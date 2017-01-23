import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import json
import decimal
import os
import time

import spotipy

LAMBDA_EXEC_TIME = 10

spotify = spotipy.Spotify()


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
    for i, t in enumerate(results['tracks']['items']):  # i unused
        return t['uri']


def get_cursor(table):
    res = table.get_item(
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


def set_cursor(table, position):
    table.put_item(
        Item={
            'name': 'rediscover',
            'position': position
        }
    )
    print '%s will be the next' % position


def get_track_from_dynamodb(table, track_id):
    res = table.get_item(
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


def handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    cursors_table = dynamodb.Table('ra_cursors')
    tracks_table = dynamodb.Table('any_tracks')

    now = begin_time = int(time.time())
    cur = get_cursor(cursors_table)

    while now < begin_time + LAMBDA_EXEC_TIME:
        # needs to be at the beginning because of all the continues
        now = int(time.time())

        cur += 1
        try:
            current_track = get_track_from_dynamodb(tracks_table, cur)
        except Exception:
            print 'no song %s' % cur
            continue

        if 'spotify' in current_track:
            continue

        try:
            spotify_uri = find_on_spotify(current_track['spotify'])
        except Exception, e:
            continue

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

        response = tracks_table.update_item(
            Key=keys,
            AttributeUpdates=attribute_updates
        )

    set_cursor(cursors_table, cur)


if __name__ == "__main__":
    print handler({}, {})
