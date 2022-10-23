import json
import warnings
import requests
import spotipy
import sys
import spotipy.util as util
from spotipy import SpotifyOAuth
import pandas as pd
import numpy as np
import seaborn as sns
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn import metrics

SPOTIFY_USERNAME = 'buttercrawl'  # 你的spotify账户名称
SPOTIFY_CLIENT_ID = '2fc4fc6df3f045ab9df8a7f63c6ccad3'  # 你在spotify developer创建的应用程序的用户id
SPOTIFY_CLIENT_SECRET = '8e51a977a5e249ae9222f4e0419f52cc'  # 你在spotify developer创建的应用程序的用户密码
SPOTIFY_REDIRECT_URI = 'http://localhost:8888/'  # 重定向网址，需要在应用程序设置里保持一致
SPOTIFY_SCOPE = 'user-library-read'  # 声明的app授权权限


class DataNotFoundException(Exception):
    pass


class TokenError(Exception):
    pass
    pass


def _getToken():
    auth_manager = SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID,
                                client_secret=SPOTIFY_CLIENT_SECRET,
                                scope=SPOTIFY_SCOPE,
                                username=SPOTIFY_USERNAME,
                                redirect_uri=SPOTIFY_REDIRECT_URI)

    sp = spotipy.Spotify(auth_manager=auth_manager)
    if sp:
        return sp
    else:
        message = 'Fail to get authorized(Perhaps the token is invalid )'
        raise TokenError(message)


class TrackInfo:
    def __init__(self, title, artist, album, genres, popularity, markets, release_date, features, image):

        self.title = title
        self.artist = artist
        self.album = album
        self.genres = genres
        self.markets = markets
        self.release_date = release_date
        self.features = features
        self.popularity = popularity
        self.image = image

    def __repr__(self):
        return "{}.{}(title={!r}, artist={!r}, album={!r},genres={!r},popularity={!r},markets={!r},release_date={!r},features={!r})".format(
            self.__class__.__module__, self.__class__.__name__,
            self.title, self.artist, self.album, self.genres, self.popularity,
            self.markets, self.release_date, self.features
        )

    def __str__(self):
        s = u" '%s' by %s from '%s'\n %s\n released at %s" \
            % (self.title, self.artist, self.album, self.genres, self.release_date)
        if sys.version_info.major < 3:
            return s.encode(getattr(sys.stdout, "encoding", "") or "utf8")
        else:
            return s


class Track:
    def __init__(self, songid, keyword, market=None, fetch=True):
        self.songid = songid
        self.keyword = keyword
        self.market = market
        self.data = {}
        if fetch:
            self._packData()

    def __repr__(self):
        if self.songid or self.keyword:
            return " {}.{}(songid={!r},keyword={!r})".format(
                self.__class__.__module__, self.__class__.__name__, self.songid, self.keyword)

    def _getTrackData(self, sp, id, market):
        resp = sp.track(track_id=id, market=market)
        if resp:
            self.data['title'] = resp['name']
            self.data['artist'] = resp['artists'][0]['name']
            self.data['album'] = resp['album']['name']
            self.data['image'] = resp['album']['images'][0]
            self.data['release_date'] = resp['album']['release_date']
            self.data['popularity'] = resp['popularity']
            self.data['markets'] = resp['available_markets']
            self.at_id = (resp['artists'][0]['uri']).split(':')[2]
        else:
            message = 'Track Not Found(Perhaps the track_id is invalid )'
            raise DataNotFound(message)

    def _getGenres(self, sp, id):
        resp = sp.artist(artist_id=id)
        self.data['genres'] = resp['genres']

    def _getFeatures(self, sp, id):
        resp = sp.audio_features(tracks=id)
        self.features = {}
        self.features['danceability'] = resp[0]['danceability']
        self.features['energy'] = resp[0]['energy']
        self.features['key'] = resp[0]['key']
        self.features['loudness'] = resp[0]['loudness']
        self.features['speechiness'] = resp[0]['speechiness']
        self.features['acousticness'] = resp[0]['acousticness']
        self.features['instrumentalness'] = resp[0]['instrumentalness']
        self.features['valence'] = resp[0]['valence']
        self.features['tempo'] = resp[0]['tempo']
        self.features['liveness'] = resp[0]['liveness']
        self.features['length'] = str((resp[0]['duration_ms']) / 1000) + 's'
        self.data['features'] = self.features

    @staticmethod
    def _searchTrack(sp, keyword):
        q = keyword.replace(' ', '%20')
        resp = sp.search(q, type='track', limit=1)
        id = (resp['tracks']['items'][0]['uri']).split(':')[2]

        return id

    def _packData(self):
        sp = _getToken()
        if self.keyword:
            self.songid = self._searchTrack(sp, self.keyword)
        self._getTrackData(sp, self.songid, market=self.market)
        self._getGenres(sp, self.at_id)
        self._getFeatures(sp, self.songid)
        data = self.data
        self.info = TrackInfo(data['title'], data['artist'], data['album'],
                              data['genres'], data['popularity'], data['markets'],
                              data['release_date'], data['features'], data['image'])


class AlbumInfo(TrackInfo):

    def __init__(self, title, artist, genres, popularity, markets, release_date, tracks, image, copyrights, label):
        self.title = title
        self.artist = artist
        self.genres = genres
        self.popularity = popularity
        self.markets = markets
        self.release_date = release_date
        self.tracks = tracks
        self.image = image
        self.copyrights = copyrights
        self.label = label
        self.album=self.title


class Album:
    def __init__(self, ab_id=None, keyword=None, fetch=True):
        self.ab_id = ab_id
        self.keyword = keyword

        self.data = {}
        if fetch:
            self._packData()

    def __repr__(self):
        if self.at_id or self.keyword:
            return " {}.{}(ab_id={!r},keyword={!r})".format(
                self.__class__.__module__, self.__class__.__name__, self.ab_id, self.keyword)

    def _getAlbumData(self, sp, id):
        resp = sp.album(album_id=id)
        if resp is not None:
            self.data['title'] = resp['name']
            self.data['artist'] = resp['artists'][0]['name']
            self.data['genres'] = resp['genres']
            self.data['popularity'] = resp['popularity']
            self.data['label'] = resp['label']
            self.data['image'] = resp['images'][0]['url']
            self.data['release_date'] = resp['release_date']
            self.data['markets'] = resp['available_markets']
            self.id = resp['artists'][0]['uri'].split(':')[2]
            cr = []
            for c in resp['copyrights']:
                cr.append(c['text'])
            cr = set(cr)
            for r in cr:
                self.data['copyrights'] = r
            tracks = []
            for i in resp['tracks']['items']:
                track = {}
                id = i['uri'].split(':')[2]
                track[id] = i['name']
                tracks.append(track)
            self.data['tracks'] = tracks
        else:
            messages = 'Can not found the Album(Perhaps the ab_id is invalid?)'
            raise DataNotFoundException(messages)

    def _getGenres(self, sp, id):
        resp = sp.artist(artist_id=id)
        self.data['genres'] = resp['genres']

    def _searchAlbum(self, sp, kw):
        q = kw.replace(' ', '%20')
        resp = sp.search(q, type='album', limit=1)
        if resp is not None:
            self.ab_id = resp['albums']['items'][0]['uri'].split(':')[2]
        else:
            messages = 'Album not found( Perhaps the name is misspelled? )'
            raise DataNotFoundException(messages)

    def _packData(self):
        sp = _getToken()
        if self.keyword is not None:
            self._searchAlbum(sp, self.keyword)

        self._getAlbumData(sp, self.ab_id)
        if len(self.data['genres'])==0 :
            self._getGenres(sp, self.id)

        data = self.data
        self.info = AlbumInfo(data['title'], data['artist'], data['genres'],
                              data['popularity'], data['markets'],
                              data['release_date'], data['tracks'],
                              data['image'], data['copyrights'], data['label'])


class ArtistInfo:
    def __init__(self, name, genres, followers, popularity, albums, image):

        self.name = name
        self.genres = genres
        self.followers = followers
        self.popularity = popularity
        self.albums = albums
        self.image = image

    def __repr__(self):
        return "{}.{}(name={!r}, genres={!r},followers={!r},popularity={!r},albums={!r},image={!r})".format(
            self.__class__.__module__, self.__class__.__name__,
            self.name, self.genres, self.followers, self.popularity, self.albums, self.image
        )

    def __str__(self):

        f = list(str(self.followers))
        f.insert(-3, ',')
        t = ''
        for ts in f:
            t += ts
        s = u"%s\n%s\n%s followers\n%d albums" \
            % (self.name, self.genres[0], t, len(self.albums))
        if sys.version_info.major < 3:
            return s.encode(getattr(sys.stdout, "encoding", "") or "utf8")
        else:
            return s


class Artist:

    def __init__(self, at_id=None, keyword=None, fetch=True):
        self.at_id = at_id
        self.keyword = keyword

        self.data = {}
        if fetch:
            self._packData()

    def __repr__(self):
        if self.at_id or self.keyword:
            return " {}.{}(at_id={!r},keyword={!r})".format(
                self.__class__.__module__, self.__class__.__name__, self.at_id, self.keyword)

    def _getArtistData(self, sp, id):

        resp = sp.artist(artist_id=id)

        if resp is not None:
            self.data['name'] = resp['name']
            self.data['genres'] = resp['genres']
            self.data['followers'] = resp['followers']['total']
            self.data['image'] = resp['images'][0]['url']
            self.data['popularity'] = resp['popularity']
        else:
            messages = 'Can not found the artist (Perhaps the at_id is invalid )'
            raise DataNotFoundException(messages)

    def _getAlbumData(self, sp, id):

        resp = sp.artist_albums(artist_id=id)
        if resp is not None:

            albums = []

            for item in resp['items']:
                album = {}
                album_id = item['uri'].split(':')[2]
                album[album_id] = item['name']
                albums.append(album)

            self.data['albums'] = albums

        else:
            messages = 'Can not found the artist (Perhaps the at_id is invalid )'
            raise DataNotFoundException(messages)

    def _searchArtist(self, sp, kw):

        q = kw.replace(' ', '%20')
        resp = sp.search(q, type='artist', limit=1)
        if resp is not None:
            item = resp['artists']['items'][0]

            self.at_id = item['uri'].split(':')[2]
        else:
            messages = 'Artist not found( Perhaps the name is misspelled? )'
            raise DataNotFoundException(messages)

    def _packData(self):
        sp = _getToken()
        if self.keyword is not None:
            self._searchArtist(sp, self.keyword)

        self._getArtistData(sp, self.at_id)
        self._getAlbumData(sp, self.at_id)
        data = self.data
        self.info = ArtistInfo(data['name'], data['genres'], data['followers'],
                               data['popularity'], data['albums'], data['image'])


disk=Album(ab_id='3y0KpeITjIkjNCEPy7nNME').info
print(disk)
