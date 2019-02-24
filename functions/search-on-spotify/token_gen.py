import json
import os
import time

import spotipy
import spotipy.util as util
import spotipy.oauth2 as oauth2

import subprocess

spotify = spotipy.Spotify()

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = 'http://localhost/'


def handler(event, context):
    scope = 'playlist-read-private playlist-modify-private'
    user = '11111204'

    sp_oauth = oauth2.SpotifyOAuth(
            SPOTIPY_CLIENT_ID,
            SPOTIPY_CLIENT_SECRET,
            SPOTIPY_REDIRECT_URI,
            scope=scope,
            cache_path='.cache-'+user
        )
    auth_url = sp_oauth.get_authorize_url()
    subprocess.call(["open", auth_url])


if __name__ == "__main__":
    print handler({}, {})
