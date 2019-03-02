import json
import os
import time

import spotipy
import spotipy.util as util
import boto3

import json
from pprint import pprint

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = 'http://localhost/'

# DB
dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
cursors_table = dynamodb.Table('ra_cursors')


def handler(event, context):
    scope = 'playlist-read-private playlist-modify-private'
    user = '11111204'

    util.prompt_for_user_token(
        username=user,
        scope=scope,
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI)

    with open('/tmp/.cache-'+user) as f:
        data = json.load(f)
    pprint(data)

    print cursors_table.put_item(
        Item={
            'name': 'token',
            'value': data
        }
    )

    print "Stored token"


if __name__ == "__main__":
    print handler({}, {})
