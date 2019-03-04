"""
Search track names on Spotify
"""

import os
import sys

# https://github.com/apex/apex/issues/639#issuecomment-455883587
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
import decimal

import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


LAMBDA_EXEC_TIME = 110
STOP_SEARCH = 50

# DB
dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
cursors_table = dynamodb.Table('ra_cursors')
tracks_table = dynamodb.Table('any_tracks')
playlists_table = dynamodb.Table('ra_playlists')

# Spotify
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_USER = os.getenv('SPOTIPY_USER')
SPOTIPY_REDIRECT_URI = 'http://localhost/'

scope = 'playlist-read-private playlist-modify-private playlist-modify-public'


def restore_spotify_token():
    res = cursors_table.get_item(
        Key={
            'name': 'token'
        },
        AttributesToGet=[
            'value'
        ]
    )
    if 'Item' not in res:
        print res
        return 0

    token = res['Item']['value']
    with open("/tmp/.cache-"+SPOTIPY_USER, "w+") as f:
        f.write("%s" % json.dumps(token, ensure_ascii=False, cls=DecimalEncoder))

    print 'Restored token: %s' % token


def store_spotify_token(token_info):
    cursors_table.put_item(
        Item={
            'name': 'token',
            'value': token_info
        }
    )
    print "Stored token: %s" % token_info


def get_spotify():
    restore_spotify_token()

    sp_oauth = oauth2.SpotifyOAuth(
            SPOTIPY_CLIENT_ID,
            SPOTIPY_CLIENT_SECRET,
            SPOTIPY_REDIRECT_URI,
            scope=scope,
            cache_path='/tmp/.cache-'+SPOTIPY_USER
        )

    token_info = sp_oauth.get_cached_token()
    token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])

    store_spotify_token(token_info)

    return spotipy.Spotify(auth=token_info['access_token'])


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def find_on_spotify(sp, ra_name):
    results = sp.search(ra_name, limit=1, type='track')
    for i, t in enumerate(results['tracks']['items']):  # i unused
        return t['uri']


def get_last_playlist_for_year(year):
    res = playlists_table.query(
        ScanIndexForward=False,
        KeyConditionExpression=Key('year').eq(year),
        Limit=1
    )
    if res['Count'] == 0:
        return
    return [res['Items'][0]['playlist_id'], res['Items'][0]['num']]


def create_playlist_for_year(sp, year, num=1):
    playlist_name = 'RA: %d' % year
    if num > 1:
        playlist_name += ' (%d)' % num
    res = sp.user_playlist_create(SPOTIPY_USER, playlist_name, public=True)
    playlists_table.put_item(
        Item={
            'year': year,
            'num': num,
            'playlist_id': res['id']
        }
    )
    return [res['id'], num]


def get_playlist(sp, year):
    return get_last_playlist_for_year(year) or create_playlist_for_year(sp, year)


def add_track_to_spotify_playlist(sp, track_spotify_uri, year):
    try:
        playlist_id, playlist_num = get_playlist(sp, year)
        sp.user_playlist_add_tracks(
            SPOTIPY_USER,
            playlist_id,
            [track_spotify_uri])
    except Exception, e:
        # if playlist is full, it will be thrown here
        # this way we don't need to explicitely count items in playlists
        if hasattr(e, 'http_status') and e.http_status in [403, 500]:
            playlist_id, = create_playlist_for_year(
                sp,
                year,
                playlist_num+1)
            # retry same fonction to use API limit logic
            add_track_to_spotify_playlist(sp, track_spotify_uri, year)
        else:
            # Reached API limit
            raise e
    return playlist_id


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
            'track_uri',
            'name',
            'first_charted_year',
            'release_date_year',
            'playlist_id'
        ]
    )
    return res['Item']


def persist_spotify_uris(track_uri, playlist_id, cur, current_track, year):
    print "%s - %s (%d) | %s in %s" % (cur, current_track['name'],
                                       year, track_uri, playlist_id)

    return tracks_table.update_item(
        Key={
            'host': 'ra',
            'id': cur
        },
        AttributeUpdates={
            'track_uri': {
                'Value': track_uri,
                'Action': 'PUT'
            },
            'playlist_id': {
                'Value': playlist_id,
                'Action': 'PUT'
            }
        }
    )


def get_min_year(current_track):
    release_date_year = current_track['release_date_year']
    if 'first_charted_year' not in current_track:
        return release_date_year
    min_year = min(release_date_year, current_track['first_charted_year'])
    if min_year < 2006:
        print min_year
        return 2006
    return min_year


def handle(event, context):
    sp = get_spotify()
    now = begin_time = int(time.time())
    cur = last_successfully_processed_song_id = get_cursor()
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
                break
            continue

        # if 'playlist_id' not in current_track:
        try:
            if 'spotify_uri' not in current_track:
                track_uri = find_on_spotify(sp, current_track['name'])
                if not track_uri:
                    continue
            else:
                track_uri = current_track['spotify_uri']
            year = get_min_year(current_track)
            playlist_id = add_track_to_spotify_playlist(sp,
                                                        track_uri,
                                                        year)
            persist_spotify_uris(track_uri, playlist_id,
                                 cur, current_track, year)
        except Exception, e:
            print e
            # stop when Spotify API limit reached
            break
        last_successfully_processed_song_id = cur

    set_cursor(last_successfully_processed_song_id)


if __name__ == "__main__":
    print handle({}, {})
