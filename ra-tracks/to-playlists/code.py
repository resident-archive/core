import json
import decimal
import os
import time

import requests
import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2

import boto3

spotify = spotipy.Spotify()

SPOTIPY_CLIENT_ID = '9ede3d42655645b4afab32238f4daf14'
SPOTIPY_CLIENT_SECRET = '1084d849881c4bdf9cb1542dd230744d'
SPOTIPY_REDIRECT_URI = 'http://localhost:8888'

user = '11111204'


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def unmarshalJson(node):
    data = {}
    data["M"] = node
    return unmarshalValue(data, True)


def unmarshalValue(node, mapAsObject):
    for key, value in node.items():
        if(key == "S" or key == "N"):
            return value
        if(key == "M" or key == "L"):
            if(key == "M"):
                if(mapAsObject):
                    data = {}
                    for key1, value1 in value.items():
                        data[key1] = unmarshalValue(value1, mapAsObject)
                    return data
            data = []
            for item in value:
                data.append(unmarshalValue(item, mapAsObject))
            return data


def get_new_song(event):
    for record in event['Records']:
        record = record['dynamodb']
        view_type = record['StreamViewType']
        if view_type == 'NEW_AND_OLD_IMAGES':
            new_song = unmarshalJson(record['NewImage'])
            if 'NewImage' in record.keys() and \
               'spotify' in record['NewImage'] and \
               record['NewImage']['spotify'] is not None:
                return (new_song['id'], new_song['spotify'])


def get_playlist_number_from_track_id(track_id):
    return track_id / 10000 + 1


def get_playlist(track_id, sp):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    table = dynamodb.Table('ra_playlists')
    playlist_number = get_playlist_number_from_track_id(track_id)
    try:
        playlist = table.get_item(
            Key={
                'id': playlist_number
            },
            AttributesToGet=[
                'spotify'
            ]
        )
        if 'spotify' in playlist['Item']:
            return playlist['Item']['spotify']
        raise
    except Exception:
        playlist_name = 'RA archive #%02d' % playlist_number
        res = sp.user_playlist_create(user, playlist_name, public=False)
        playlist_id = res['id']
        response = table.put_item(
            Item={
                'id': playlist_number,
                'spotify': playlist_id
            }
        )
        return playlist_id


def handler(event, context):
    scope = 'playlist-read-private playlist-modify-private'

    sp_oauth = oauth2.SpotifyOAuth(
            SPOTIPY_CLIENT_ID,
            SPOTIPY_CLIENT_SECRET,
            SPOTIPY_REDIRECT_URI,
            scope=scope,
            cache_path='tmp/.cache-'+user
        )

    token = sp_oauth.get_cached_token()
    if not token:
        # This token is to manually get from token.py and set as an env. var
        code = os.environ.get('CODE') or event.get('CODE')
        token = sp_oauth.get_access_token(code)
    sp = spotipy.Spotify(auth=token['access_token'])

    new_song = get_new_song(event)
    if new_song:
        playlist = get_playlist(int(new_song[0]), sp)
        res = sp.user_playlist_add_tracks(user, playlist, [new_song[1]])
        print 'Added %s to %s' % (new_song, playlist)

    return json.dumps({}, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    # Test event
    os.environ['CODE'] = 'AQCt7CzvHe9FgS7PJHgmkMy4TY1NGv8wVp4eLW76y5FIBNY21_8JkUXhasLm7x2_EpJxuzeEjeeVEqlF8UO1p1brgpuAgbXYznmdLFSq3X_DgD52GL3SelTlT81KTxWMXG2M1GWPH97myG0Vu-boKp8Y_P8i_3HI6lO-G-uAQQEZSsON_xO6PtzhPvDwydj2QLs3I8govJIWBCed0fU3qreza50JUP4Lru0l0Ccisrm_KyXWNPvQi0VEZg'
    ddb_trigger = {u'Records': [{u'eventID': u'81c853e71fae9e3d1551b8cc18ee1154', u'eventVersion': u'1.1', u'dynamodb': {u'OldImage': {u'ra_name': {u'S': u'E- Contact - Banna'}, u'spotify': {u'NULL': True}, u'added': {u'N': u'1484513528'}, u'id': {u'N': u'4154'}}, u'SequenceNumber': u'6840700000000016069156787', u'Keys': {u'id': {u'N': u'4154'}}, u'SizeBytes': 103, u'NewImage': {u'ra_name': {u'S': u'E- Contact - Banna'}, u'spotify': {u'S': u'spotify:track:25b9gwBYaSzwZwwJuTR3Xh'}, u'added': {u'N': u'1484596565'}, u'id': {u'N': u'4154'}}, u'ApproximateCreationDateTime': 1484596560.0, u'StreamViewType': u'NEW_AND_OLD_IMAGES'}, u'awsRegion': u'eu-west-1', u'eventName': u'MODIFY', u'eventSourceARN': u'arn:aws:dynamodb:eu-west-1:705440408593:table/tracks/stream/2017-01-15T16:17:34.299', u'eventSource': u'aws:dynamodb'}]}
    print handler(ddb_trigger, {})
