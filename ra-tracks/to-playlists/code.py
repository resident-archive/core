import json
import decimal
import os
import time

import requests
import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2
import ast

spotify = spotipy.Spotify()

SPOTIPY_CLIENT_ID = '9ede3d42655645b4afab32238f4daf14'
SPOTIPY_CLIENT_SECRET = '1084d849881c4bdf9cb1542dd230744d'
SPOTIPY_REDIRECT_URI = 'http://localhost:8888'


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


def handler(event, context):
    # print ast.literal_eval(event)

    for record in event['Records']:
        record = record['dynamodb']
        view_type = record['StreamViewType']
        if view_type == 'NEW_AND_OLD_IMAGES':
            old = unmarshalJson(record['OldImage'])
            new = unmarshalJson(record['NewImage'])
            if new['spotify'] is not (None and old['spotify']):
                track_to_add = new['spotify']
                print track_to_add

    scope = 'playlist-read-private playlist-modify-private'
    user = '11111204'

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
    playlist = sp.user_playlist(user, '439JHHifFXBMOtaLnWuxis')
    print playlist
    sp.user_playlist_add_tracks(user, '439JHHifFXBMOtaLnWuxis', [track_to_add])
    return json.dumps({}, indent=4, cls=DecimalEncoder)
    return 'done'


if __name__ == "__main__":
    os.environ['CODE'] = 'AQAUrQoa4Imir2ZBpTyswaakF2TfCyNDu7go6MNRNgtWZ4llH7Sifr4WMWUK78fDEMRZl0B5bT9mV6FZvSR60DOT11xHWBl2rRRc6XLC-VOJTnsR9wrg1qYiRQ99A0SS1S5xHnLjNdRi8x1ZN0jr-hbfKi6jjRmZL6NBedK6dpHvJ86Z-beVOSnaa6t1aBYz6_Fa-iDqkpYLIFbFYEbjTJIJ95CaSEL9kmmEXVxyFAbBxNMf8OauOxbrgw'
    ddb_trigger = {u'Records': [{u'eventID': u'81c853e71fae9e3d1551b8cc18ee1154', u'eventVersion': u'1.1', u'dynamodb': {u'OldImage': {u'ra_name': {u'S': u'E- Contact - Banna'}, u'spotify': {u'NULL': True}, u'added': {u'N': u'1484513528'}, u'id': {u'N': u'4154'}}, u'SequenceNumber': u'6840700000000016069156787', u'Keys': {u'id': {u'N': u'4154'}}, u'SizeBytes': 103, u'NewImage': {u'ra_name': {u'S': u'E- Contact - Banna'}, u'spotify': {u'S': u'spotify:track:25b9gwBYaSzwZwwJuTR3Xh'}, u'added': {u'N': u'1484596565'}, u'id': {u'N': u'4154'}}, u'ApproximateCreationDateTime': 1484596560.0, u'StreamViewType': u'NEW_AND_OLD_IMAGES'}, u'awsRegion': u'eu-west-1', u'eventName': u'MODIFY', u'eventSourceARN': u'arn:aws:dynamodb:eu-west-1:705440408593:table/tracks/stream/2017-01-15T16:17:34.299', u'eventSource': u'aws:dynamodb'}]}
    print handler(ddb_trigger, {})
