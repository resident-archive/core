"""
Fetch all RA tracks from 1 to +oo
"""

import os
import sys

# https://github.com/apex/apex/issues/639#issuecomment-455883587
file_path = os.path.dirname(__file__)
module_path = os.path.join(file_path, "env")
sys.path.append(module_path)

import boto3
from boto3.dynamodb.conditions import Key, Attr

import json
import decimal
import time

from bs4 import BeautifulSoup
import requests
import re

LAMBDA_EXEC_TIME = os.getenv('LAMBDA_EXEC_TIME', 50)
PERSIST_DATA = os.getenv('PERSIST_DATA', True)
BEGIN_YEAR = 2006

dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
table = dynamodb.Table('any_tracks')
cursors_table = dynamodb.Table('ra_cursors')


def url_at_index(index):
    return 'https://ra.co/tracks/' + str(index)


def page_string(url):
    """Request a webpage"""
    r = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0'
    })

    if r.status_code == 200:
        for hist in r.history:
            if hist.status_code != 200:
                raise Exception(hist)
        return r.text
    else:
        raise Exception(r)


def extract_track_info(page, last_year):
    title = page.find('h1').getText()

    release_date_year, release_date = get_release_date_element(page, last_year)
    first_charted_year, first_charted_date, first_charted_by = get_first_charted_elements(page)

    fields = {
        'title': title,
        'release_date_year': release_date_year,
        'release_date': release_date,
        'first_charted_year': first_charted_year,
        'first_charted_date': first_charted_date,
        'charted_by': first_charted_by,
        'label':  get_generic_element(page, "Label /"),
        'most_popular_month': get_generic_element(page, "Most popular month /"),
        'times_charted': get_generic_element(page, "Times charted /"),
        'also_charted_by': get_generic_element(page, "Also charted by /")
    }

    return fields


def get_release_date_element(page, last_year):
    try:
        release_date = page.find_all(text=re.compile("Release Date /"))
        release_date = release_date[0].parent.parent
        release_date.div.decompose()
        release_date = release_date.getText().strip()
        release_date_year = int(release_date[-4:])
    except Exception:
        release_date_year = last_year
        release_date = None

    return release_date_year, release_date


def get_first_charted_elements(page):
    try:
        first_charted_element = page.find_all(text=re.compile("First charted /"))
        first_charted_element = first_charted_element[0].parent.parent
        first_charted_element.div.decompose()
        first_charted_by_link = first_charted_element.a
        first_charted_by = first_charted_by_link.getText()
        first_charted_element.a.decompose()
        first_charted_date = first_charted_element.getText().strip()[:-3]
        first_charted_year = int(first_charted_date[-4:])
    except Exception:
        first_charted_year = None
        first_charted_date = None
        first_charted_by = None

    return first_charted_year, first_charted_date, first_charted_by


def get_generic_element(page, label):
    try:
        also_charted_by = page.find_all(text=re.compile(label))
        also_charted_by = also_charted_by[0].parent.parent
        also_charted_by.div.decompose()
        return also_charted_by.getText().strip()
    except Exception:
        return None


def get_song_from_index(index, last_year=BEGIN_YEAR):
    url = url_at_index(index)
    try:
        content = page_string(url)
    except Exception:
        os.environ['last'] = str(index + 1)
        raise
    page = BeautifulSoup(content, 'html.parser')
    return extract_track_info(page, last_year)


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def get_cursor():
    loop = cursors_table.get_item(
        Key={
            'name': 'loop'
        },
        AttributesToGet=[
            'position'
        ]
    )

    year = cursors_table.get_item(
        Key={
            'name': 'last_year'
        },
        AttributesToGet=[
            'value'
        ]
    )

    if 'Item' not in loop or 'Item' not in year:
        return 0, BEGIN_YEAR

    return loop['Item']['position'], year['Item']['value']


def set_cursor(position, year):
    cursors_table.put_item(
        Item={
            'name': 'loop',
            'position': position
        }
    )
    cursors_table.put_item(
        Item={
            'name': 'last_year',
            'value': year
        }
    )


def handle(event, context):
    """
    Lambda handler
    """
    if PERSIST_DATA:
        current_id, last_year = get_cursor()
    else:
        current_id = 0
        last_year = BEGIN_YEAR

    response = None
    now = begin_time = int(time.time())

    while now < begin_time + LAMBDA_EXEC_TIME:
        # needs to be at the beginning because of all the continues
        now = int(time.time())
        current_id += 1
        try:
            fields = get_song_from_index(current_id, last_year)
        except Exception as e:
            print(e)
            continue

        item = {
            'host': 'ra',
            'id': current_id,
            'name': fields['title']
        }

        if fields['first_charted_year']:
            item['first_charted_year'] = fields['first_charted_year']
        if fields['release_date_year']:
            item['release_date_year'] = fields['release_date_year']

        extra_fields = {
            'release_date': fields['release_date'] if 'release_date' in fields else None,
            'first_charted_date': fields['first_charted_date'] if 'first_charted_date' in fields else None,
            'charted_by': fields['first_charted_by'] if 'first_charted_by' in fields else None,
            'label': fields['label'] if 'label' in fields else None,
            'most_popular_month': fields['most_popular_month'] if 'most_popular_month' in fields else None,
            'times_charted': fields['times_charted'] if 'times_charted' in fields else None,
            'also_charted_by': fields['also_charted_by'] if 'also_charted_by' in fields else None
        }

        item['extra_fields'] = {k: v for k, v in extra_fields.items() if v is not None}

        print("%s - %s (%d)" % (current_id, fields['title'], fields['release_date_year']))

        if PERSIST_DATA:
            key = {
                'host': 'ra',
                'id': current_id
            }
            existing_item = table.get_item(Key=key)
            if 'Item' in existing_item:
                response = table.update_item(
                    Key=key,
                    UpdateExpression="set extra_fields = :extra_fields, updated = :updated",
                    ExpressionAttributeValues={
                        ':extra_fields': item['extra_fields'],
                        ':updated': now,
                    }
                )
            else:
                item['added'] = now
                response = table.put_item(Item=item)
            set_cursor(current_id, fields['release_date_year'])

    if response:
        return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print(handle({}, {}))
