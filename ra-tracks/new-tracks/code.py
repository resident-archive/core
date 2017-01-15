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

spotify = spotipy.Spotify()


def url_at_index(index):
    return 'https://www.residentadvisor.net/tracks/' + str(index)


def stringified_page(url):
    '''
    Request a webpage
    '''
    r = requests.get(url)

    if r.status_code == 200:
        for hist in r.history:
            if hist.status_code != 200:
                raise Exception(r.status_code)
        return r.text
    else:
        raise Exception(r.status_code)


def get_song_with_index(index):
    url = url_at_index(index)
    try:
        content = stringified_page(url)
    except Exception:
        os.environ['last'] = str(index + 1)
        raise
    page = BeautifulSoup(content, 'html.parser')
    return page.find('h1').getText()


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


def handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    table = dynamodb.Table('tracks')

    begin_time = int(time.time())
    now = int(time.time())
    while now < begin_time + 40:
        current_id = int(os.environ.get('last') or event.get('last'))
        try:
            ra_name = get_song_with_index(current_id)
        except Exception:
            continue

        spotify_uri = find_on_spotify(ra_name)

        print "%s - %s | %s" % (current_id, ra_name, spotify_uri)

        response = table.put_item(
           Item={
                'id': current_id,
                'added': now,
                'ra_name': ra_name,
                'spotify': spotify_uri
            }
        )
        now = int(time.time())
        os.environ['last'] = str(current_id + 1)

    return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print handler({'last': 1}, {})
