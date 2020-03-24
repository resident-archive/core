"""
Fetch all RA tracks from 1 to +oo
"""
import os
import sys

# https://github.com/apex/apex/issues/639#issuecomment-455883587
file_path = os.path.dirname(__file__)
module_path = os.path.join(file_path, "env")
sys.path.append(module_path)

from spotipy.oauth2 import SpotifyClientCredentials
from pprint import pprint

import urllib.parse
from bs4 import BeautifulSoup
import requests
import musicbrainzngs
import spotipy
import re
import boto3

dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
any_tracks = dynamodb.Table('any_tracks')


def stringified_page(url):
    """Request a webpage"""
    r = requests.get(url)

    if r.status_code == 200:
        for hist in r.history:
            if hist.status_code != 200:
                raise Exception(r.status_code)
        return r.text
    else:
        raise Exception(r.status_code)


def extract_track_info(page):
    soup = BeautifulSoup(page, 'html.parser')

    twitter = None
    twitters = soup.find_all(text=re.compile("Twitter"))
    if len(twitters) > 1:
        twitter = twitters[0].parent.get('href')
    return twitter


def find_artist_ra(artist):
    artist = artist.replace(" ", "")
    try:
        p = stringified_page("https://www.residentadvisor.net/dj/" + artist)
    except Exception as e:
        return
    return extract_track_info(p)


def find_artist_musicbrainz(artist):
    artists = musicbrainzngs.search_artists(query=artist)
    if artists['artist-count'] > 0:
        artist = musicbrainzngs.get_artist_by_id(artists['artist-list'][0]["id"], includes=["url-rels"])
        artist = artist['artist']
        if 'url-relation-list' in artist and len(artist['url-relation-list']) > 1:
            for link in artist['url-relation-list']:
                target = link['target']
                if re.search('twitter', target, re.IGNORECASE):
                    return target


def find_twitter(artist):
    twitter_username = find_artist_musicbrainz(artist) or find_artist_ra(artist)
    if twitter_username:
        return urllib.parse.urlparse(twitter_username)[2].rpartition('/')[2]


def get_genres(sp, album_id, artists):
    album = sp.album(album_id)
    song_genres = album['genres']
    print("release genres:", song_genres)
    for artist in artists:
        info = sp.artist(artist['id'])
        song_genres = song_genres + info['genres']
    song_genres = [g.replace(" ", "").replace("-", "") for g in song_genres]
    print("artist genres", song_genres)
    return song_genres


def remove_duplicates_insensitive(input_list):
    output_list = []
    marker = set()

    for item in input_list:
        item_low = item.lower()
        if item_low not in marker:  # test presence
            marker.add(item_low)
            output_list.append(item)  # preserve order

    return output_list


def find_artists_twitters(artists):
    artists = [a['name'] for a in artists]
    found_one = False

    for i, artist in enumerate(artists):
        twitter = find_twitter(artist)
        if twitter:
            artists[i] = '@' + twitter
            found_one = found_one or True

    artists = remove_duplicates_insensitive(artists)
    return artists, found_one


def mark_as_tweeted(record, tweet_id):
    update_expr = "set tweet_id = :tweet_id"
    expr_attrs = {
        ':tweet_id': tweet_id
    }
    any_tracks.update_item(
        Key={
            'host': 'ra',
            'id': record['Keys']['id']
        },
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_attrs
    )


def tweet(track):
    import twitter
    api = twitter.Api(consumer_key=os.environ['TWITTER_CONSUMER_KEY'],
                      consumer_secret=os.environ['TWITTER_CONSUMER_SECRET'],
                      access_token_key=os.environ['TWITTER_ACCESS_TOKEN_KEY'],
                      access_token_secret=os.environ['TWITTER_ACCESS_TOKEN_SECRET'])

    if len(track['genres']) > 0:
        genres = " #%s" % ' #'.join(track['genres'])
    else:
        genres = ""

    txt = ('Track "%s" by %s just added to the @ResidentArchive %s playlist on Spotify%s #electronicmusic %s'
           % (track['name'],
              ', '.join(track['artists']),
              track['year'],
              genres,
              track['playlist_url'],))
    print(txt)
    # print("{name: >60}\t{twitter: >40}".format(name=track['name'], twitter=(twitter or "")))

    try:
        return api.PostUpdate(txt)
    except twitter.error.TwitterError as e:
        for msg in e.message:
            # don't raise if tweet is duplicate (187)
            if msg['code'] != 187:
                raise e


def tweet_record(spotify_track, year, playlist_id):
    musicbrainzngs.set_useragent("Resident Archive", "1.0", "https://residentarchive.com")

    spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
    track = spotify.track(spotify_track)
    artists, found_one = find_artists_twitters(track['artists'])

    if found_one:
        return tweet({
            'artists': artists,
            'name': track['name'],
            'year': year,
            'playlist_url': 'https://open.spotify.com/playlist/' + playlist_id,
            'genres': get_genres(spotify, track['album']['id'], track['artists'])[:2]
        })


def handle(event, context):
    """
    Lambda handler
    """
    if 'Records' not in event:
        return

    # Process last RA tracks added to DynamoDB stream
    for record in event['Records']:
        if record['eventSource'] != "aws:dynamodb" \
                or record['eventName'] == "INSERT":
            continue

        image = record['dynamodb']['NewImage']
        if 'release_date_year' in image \
                and 'spotify_track' in image \
                and 'spotify_playlist' in image \
                and 'tweet_id' not in image:
            year = image['release_date_year']['N']
            spotify_track = image['spotify_track']['S']
            spotify_playlist = image['spotify_playlist']['S']
            resp = tweet_record(spotify_track, year, spotify_playlist)
            if resp:
                mark_as_tweeted(record['dynamodb'], resp.id)


if __name__ == "__main__":
    print(handle({u'Records': [
        {u'dynamodb': {u'Keys': {u'host': {u'S': u'ra'},
                                 u'id': {u'N': u'956790'}},
                       u'NewImage': {u'spotify_track': {u'S': u'spotify:track:2xG4qpmeaQvLFt4AuFbKEu'},
                                     u'spotify_playlist': {u'S': u'1VHpfwF7HNqZavzg7EIBVM'},
                                     u'release_date_year': {u'N': u'2007'},
                                     u'first_charted_year': {u'N': u'2006'}},
                       u'ApproximateCreationDateTime': 1558178610.0,
                       u'StreamViewType': u'NEW_AND_OLD_IMAGES'},
         u'awsRegion': u'eu-west-1',
         u'eventName': u'MODIFY',
         u'eventSourceARN': u'arn:aws:dynamodb:eu-west-1:705440408593:table/any_tracks/stream/2019-05-06T10:02:12.102',
         u'eventSource': u'aws:dynamodb'}
    ]}, {}))
