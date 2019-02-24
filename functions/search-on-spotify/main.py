"""
Search track names on Spotify
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
import os
import time

import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2

LAMBDA_EXEC_TIME = 110
STOP_SEARCH = 50

# DB
dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
cursors_table = dynamodb.Table('ra_cursors')
tracks_table = dynamodb.Table('any_tracks')

# Spotify
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = 'http://localhost/'

scope = 'playlist-read-private playlist-modify-private'
user = '11111204'

sp_oauth = oauth2.SpotifyOAuth(
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
        scope=scope,
        cache_path='./tmp/.cache-'+user
    )

token = sp_oauth.get_cached_token()
if not token:
    # This token is to manually get from token.py and set as an env. var
    code = os.environ.get('CODE') or event.get('CODE')
    token = sp_oauth.get_access_token(code)
sp = spotipy.Spotify(auth=token['access_token'])


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def find_on_spotify(spotify, ra_name):
    results = spotify.search(ra_name, limit=1, type='track')
    for i, t in enumerate(results['tracks']['items']):  # i unused
        return t['uri']


def get_cursor():
    res = cursors_table.get_item(
        Key={
            'name': 'rediscover'
        },
        AttributesToGet=[
            'position'
        ]
    )
    if 'Item' not in res:
        return 0

    cur = res['Item']['position']
    print 'Starting at %d' % cur
    return cur


def set_cursor(position):
    cursors_table.put_item(
        Item={
            'name': 'rediscover',
            'position': position
        }
    )
    print '%s will be the next' % position


def get_track_from_dynamodb(track_id):
    res = tracks_table.get_item(
        Key={
            'host': 'ra',
            'id': track_id
        },
        AttributesToGet=[
            'spotify',
            'name'
        ]
    )
    return res['Item']


def persist_spotify_uri(spotify_uri, cur, current_track):
    keys = {
        'host': 'ra',
        'id': cur
    }
    attribute_updates = {
        'spotify': {
            'Value': spotify_uri,
            'Action': 'PUT'
        }
    }

    print "%s - %s | %s" % (cur, current_track['name'], spotify_uri)

    return tracks_table.update_item(
        Key=keys,
        AttributeUpdates=attribute_updates
    )

def handle(event, context):
    now = begin_time = int(time.time())
    cur = last_retrieved_song_id = get_cursor()
    missing_song_in_a_row_count = 0

    while now < begin_time + LAMBDA_EXEC_TIME:
        now = int(time.time())
        cur += 1

        try:
            current_track = get_track_from_dynamodb(cur)
            missing_song_in_a_row_count = 0
        except Exception:
            # no song for that ID
            missing_song_in_a_row_count += 1
            if missing_song_in_a_row_count == STOP_SEARCH:
                print "Looks like the end of the list"
                return
            continue

        last_retrieved_song_id = cur

        if 'spotify' in current_track:
            # possible to not get those in the query?
            continue

        try:
            spotify_uri = find_on_spotify(sp, current_track['name'])
        except Exception, e:
            print e
            # stop when Spotify API limit reached
            break

        if not spotify_uri:
            continue

        persist_spotify_uri(spotify_uri, cur, current_track)

    set_cursor(last_retrieved_song_id)


if __name__ == "__main__":
    print handle({}, {})
