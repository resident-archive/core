"""
Fetch all RA tracks from 1 to +oo
"""

# As set in requirements.txt, this is to use libraries in env/ instead of .
import os
import sys
file_path = os.path.dirname(__file__)
module_path = os.path.join(file_path, "env")
sys.path.append(module_path)

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import json
import decimal
import time

from bs4 import BeautifulSoup
import urlparse
import requests
import re

LAMBDA_EXEC_TIME = os.getenv('LAMBDA_EXEC_TIME', 50)
PERSIST_DATA = os.getenv('PERSIST_DATA', True)


def url_at_index(index):
    return 'https://www.residentadvisor.net/tracks/' + str(index)


def stringified_page(url):
    '''Request a webpage'''
    r = requests.get(url)

    if r.status_code == 200:
        for hist in r.history:
            if hist.status_code != 200:
                raise Exception(r.status_code)
        return r.text
    else:
        raise Exception(r.status_code)


def extract_track_info(page):
    date = page.find_all(text=re.compile("Release Date /"))
    title = page.find('h1').getText()

    date = page.find_all(text=re.compile("First charted /"))
    first_charted_element = date[0].parent.parent
    first_charted_element.div.decompose()
    first_charted_element.a.decompose()

    first_charted_year = first_charted_element.getText().strip()[-7:][:4]

    return (title, first_charted_year)


def get_song_from_index(index):
    url = url_at_index(index)
    try:
        content = stringified_page(url)
    except Exception:
        os.environ['last'] = str(index + 1)
        raise
    page = BeautifulSoup(content, 'html.parser')
    return extract_track_info(page)


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def get_last_parsed_track(table):
    res = table.query(
        ScanIndexForward=False,
        KeyConditionExpression=Key('host').eq('ra'),
        Limit=1
    )
    if res['Count'] == 0:
        return 0
    return res['Items'][0]['id']


def handle(event, context):
    """
    Lambda handler
    """
    if PERSIST_DATA:
        dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
        table = dynamodb.Table('any_tracks')
        current_id = int(get_last_parsed_track(table))
    else:
        current_id = 1

    now = begin_time = int(time.time())

    while now < begin_time + LAMBDA_EXEC_TIME:
        # needs to be at the beginning because of all the continues
        now = int(time.time())

        current_id += 1
        try:
            ra_name, first_charted_year = get_song_from_index(current_id)
        except Exception:
            continue

        item = {
            'host': 'ra',
            'id': str(current_id),
            'added': now,
            'name': ra_name,
            'first_charted_year': first_charted_year
        }

        print "%s - %s (%s)" % (str(current_id), ra_name, first_charted_year)

        if PERSIST_DATA:
            response = table.put_item(Item=item)

    if PERSIST_DATA:
        return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print handle({}, {})
