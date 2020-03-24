#!/usr/bin/python3.7

"""
Set all playlist descriptions.

Example result:

Resident Advisor Archive www.residentarchive.com @residentarchive
"""

import boto3
import spotipy
from pprint import pprint

dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
ra_playlists = dynamodb.Table('ra_playlists')

sp = spotipy.Spotify(auth_manager=spotipy.SpotifyOAuth(scope='playlist-modify-public playlist-modify-private'))

# Get all
playlists = ra_playlists.scan()
pprint(len(playlists['Items']))

for p in playlists['Items']:
    desc = "Resident Advisor Archive www.residentarchive.com @residentarchive"
    print(p.get('spotify_playlist'), desc)
    sp.user_playlist_change_details(None, p.get('spotify_playlist'), description=desc)