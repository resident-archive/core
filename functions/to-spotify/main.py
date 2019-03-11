"""
Search track names on Spotify
"""

import os
import sys

# https://github.com/apex/apex/issues/639#issuecomment-455883587
file_path = os.path.dirname(__file__)
module_path = os.path.join(file_path, "env")
sys.path.append(module_path)

# https://stackoverflow.com/a/39293287/1515819
reload(sys)
sys.setdefaultencoding('utf8')


import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from sets import Set

import json
import decimal
import os
import time
import decimal

import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2


# custom exceptions
class SpotifyTrackNotFoundException(Exception):
    pass


class RATrackNotFoundException(Exception):
    pass


class EndOfListException(Exception):
    pass


class SpotifyAPILimitException(Exception):
    pass


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


class TrackName(str):
    def __new__(cls, content):
        return str.__new__(cls, ' '.join(content.split()))  # sanitize

    def split_artist_and_track_name(self):
        return self.split(" - ", 1)

    @staticmethod
    def has_question_marks_only(str):
        allowed_chars = Set('?')
        return Set(str).issubset(allowed_chars)

    def has_missing_artist_or_name(self):
        artist, track_name = self.split_artist_and_track_name()
        return TrackName.has_question_marks_only(artist) or \
            TrackName.has_question_marks_only(track_name)


LAMBDA_EXEC_TIME = 110
STOP_SEARCH = 50
PLAYLIST_EXPECTED_MAX_LENGTH = 11000

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
        f.write("%s" % json.dumps(token,
                                  ensure_ascii=False,
                                  cls=DecimalEncoder))

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
    (artist, track_name) = ra_name
    query = 'track:"%s"+artist:"%s"' % (track_name, artist)
    try:
        results = sp.search(query, limit=1, type='track')
    except Exception, e:
        # stop when Spotify API limit reached
        raise SpotifyAPILimitException
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
    return get_last_playlist_for_year(year) or \
           create_playlist_for_year(sp, year)


def playlist_seems_full(exception, sp, playlist_id):
    if not (hasattr(exception, 'http_status') and e.http_status in [403, 500]):
        return False
    # only query Spotify total as a last resort
    # https://github.com/spotify/web-api/issues/1179
    playlist = sp.user_playlist(SPOTIPY_USER, playlist_id, "tracks")
    total = playlist["tracks"]["total"]
    return total == PLAYLIST_EXPECTED_MAX_LENGTH


def add_track_to_spotify_playlist(sp, track_spotify_uri, year):
    try:
        playlist_id, playlist_num = get_playlist(sp, year)
        sp.user_playlist_add_tracks(SPOTIPY_USER,
                                    playlist_id,
                                    [track_spotify_uri])
    except Exception, e:
        if playlist_seems_full(e, sp, playlist_id):
            playlist_id, = create_playlist_for_year(sp,
                                                    year,
                                                    playlist_num+1)
            # retry same fonction to use API limit logic
            add_track_to_spotify_playlist(sp, track_spotify_uri, year)
        else:
            # Reached API limit
            raise SpotifyAPILimitException
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

    return res['Item']['position']


def set_cursor(position):
    cursors_table.put_item(
        Item={
            'name': 'rediscover',
            'position': position
        }
    )


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


def add_put_attribute(attributes, attribute_name, attribute_value):
    if attribute_value:
        attributes[attribute_name] = {
            'Value': attribute_value,
            'Action': 'PUT'
        }
    return attributes


def persist_track(cur, current_track, year,
                  track_uri=None,
                  playlist_id=None,
                  question_marks=None):
    attribute_updates = {}
    add_put_attribute(attribute_updates, 'track_uri', track_uri)
    add_put_attribute(attribute_updates, 'playlist_id', playlist_id)
    add_put_attribute(attribute_updates, 'question_marks', question_marks)

    if question_marks:
        print "%s - %s (%d) | ??????" % (cur, current_track['name'], year)
    else:
        print "%s - %s (%d) | %s in %s" % (cur, current_track['name'],
                                           year, track_uri, playlist_id)

    return tracks_table.update_item(
        Key={
            'host': 'ra',
            'id': cur
        },
        AttributeUpdates=attribute_updates
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


def handle_index(index, sp):
    try:
        current_track = get_track_from_dynamodb(index)
    except Exception:
        raise RATrackNotFoundException
    track = TrackName(current_track['name'])
    year = get_min_year(current_track)
    if track.has_missing_artist_or_name():
        persist_track(index, current_track, year, question_marks=True)
    else:
        # if 'playlist_id' not in current_track:
        if 'spotify_uri' not in current_track:
            track_uri = find_on_spotify(sp,
                                        track.split_artist_and_track_name())
            if not track_uri:
                raise SpotifyTrackNotFoundException
        else:
            track_uri = current_track['spotify_uri']

        playlist_id = add_track_to_spotify_playlist(sp, track_uri, year)
        persist_track(index, current_track, year,
                      track_uri=track_uri,
                      playlist_id=playlist_id)


def handle(event, context):
    sp = get_spotify()
    now = begin_time = int(time.time())
    index = get_cursor()
    missing_song_in_a_row_count = 0

    while now < begin_time + LAMBDA_EXEC_TIME:
        index += 1
        try:
            handle_index(index, sp)
            missing_song_in_a_row_count = 0
        except RATrackNotFoundException as e:
            missing_song_in_a_row_count += 1
            if missing_song_in_a_row_count == STOP_SEARCH:
                raise EndOfListException
        except SpotifyTrackNotFoundException as e:
            pass
        except EndOfListException as e:
            print 'Looks like the end of the list'
            break
        except SpotifyAPILimitException as e:
            print e
            break
        finally:
            now = int(time.time())
        set_cursor(index)


if __name__ == "__main__":
    print handle({}, {})
