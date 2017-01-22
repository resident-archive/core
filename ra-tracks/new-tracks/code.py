import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import json
import decimal
import os
import time

from bs4 import BeautifulSoup
import urlparse
import requests
import spotipy

LAMBDA_EXEC_TIME = 40

spotify = spotipy.Spotify()


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
    date = page.find_all(string="Release Date /", limit=1)
    title = page.find('h1').getText()
    release_element = date[0].parent.parent
    release_element.div.decompose()
    release_date = release_element.getText().strip()
    return (title, release_date)


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


def find_on_spotify(ra_name):
    results = spotify.search(ra_name, limit=1, type='track')
    for i, t in enumerate(results['tracks']['items']):
        return t['uri']


def get_last_parsed_track(table):
    res = table.query(
        ScanIndexForward=False,
        KeyConditionExpression=Key('host').eq('ra'),
        Limit=1
    )
    if res['Count'] == 0:
        return 0
    return res['Items'][0]['id']


def handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    table = dynamodb.Table('any_tracks')

    begin_time = int(time.time())
    now = int(time.time())
    current_id = get_last_parsed_track(table)

    while now < begin_time + LAMBDA_EXEC_TIME:
        current_id += 1
        try:
            ra_name, release_date = get_song_from_index(current_id)
        except Exception:
            continue

        spotify_uri = find_on_spotify(ra_name)
        item = {
            'host': 'ra',
            'id': current_id,
            'added': now,
            'name': ra_name,
            'release_date': release_date
        }
        if spotify_uri:
            item['spotify'] = spotify_uri

        print "%s - %s (%s) | %s" % (current_id, ra_name,
                                     release_date, spotify_uri)

        response = table.put_item(Item=item)
        now = int(time.time())

    return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print handler({}, {})
