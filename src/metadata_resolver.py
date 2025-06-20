"""
Metadata Resolver für MP3 Tagger

Integriert verschiedene APIs zur Metadaten-Anreicherung:
- MusicBrainz: Primäre Musikdatenbank
- Last.fm: Genre und zusätzliche Informationen
- Spotify: Alternative Metadatenquelle
"""

import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import musicbrainzngs as mb
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from .config_manager import get_config
from .utils.string_matching import (
    match_artist_title, 
    extract_artist_variations, 
    extract_title_variations,
    clean_genre,
    extract_year_from_string
)

logger = logging.getLogger(__name__)


@dataclass
class MetadataResult:
    """Ergebnis einer Metadaten-Abfrage."""
    source: str
    confidence: float
    artist: Optional[str] = None
    title: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genres: List[str] = None
    duration: Optional[int] = None
    musicbrainz_id: Optional[str] = None
    spotify_id: Optional[str] = None
    spotify_artist_followers: Optional[int] = None
    spotify_preview_url: Optional[str] = None
    lastfm_url: Optional[str] = None
    popularity: Optional[int] = None
    explicit: Optional[bool] = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class MetadataResolver:
    """Löst Metadaten über verschiedene APIs auf."""
    
    def __init__(self):
        """Initialisiert den MetadataResolver."""
        self.config = get_config()
        self._setup_apis()
        
    def _setup_apis(self):
        """Konfiguriert die API-Clients."""
        # MusicBrainz Setup
        user_agent = self.config.get('api_keys.musicbrainz_user_agent')
        if user_agent:
            mb.set_useragent(
                app="MP3Tagger",
                version="1.0.0",
                contact=user_agent
            )
        
        # Spotify Setup
        spotify_client_id = self.config.get_api_key('spotify_client_id')
        spotify_client_secret = self.config.get_api_key('spotify_client_secret')
        
        self.spotify = None
        if spotify_client_id and spotify_client_secret:
            try:
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret
                )
                self.spotify = spotipy.Spotify(
                    client_credentials_manager=client_credentials_manager
                )
                logger.info("Spotify API erfolgreich initialisiert")
            except Exception as e:
                logger.warning(f"Spotify API Initialisierung fehlgeschlagen: {e}")
        else:
            logger.info("Spotify API-Keys nicht konfiguriert")
        
        # Last.fm API Key
        self.lastfm_api_key = self.config.get_api_key('lastfm_api_key')
        if self.lastfm_api_key:
            logger.info("Last.fm API konfiguriert")
        else:
            logger.info("Last.fm API-Key nicht konfiguriert")
    
    async def resolve_metadata(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> List[MetadataResult]:
        """
        Löst Metadaten für einen Song über alle verfügbaren APIs auf.
        
        Args:
            artist: Künstlername
            title: Songtitel
            album: Album (optional)
            
        Returns:
            Liste von MetadataResult-Objekten sortiert nach Confidence-Score
        """
        results = []
        
        # Parallele API-Anfragen
        tasks = []
        
        # MusicBrainz
        tasks.append(self._query_musicbrainz(artist, title, album))
        
        # Spotify
        if self.spotify:
            tasks.append(self._query_spotify(artist, title, album))
        
        # Last.fm
        if self.lastfm_api_key:
            tasks.append(self._query_lastfm(artist, title))
        
        # Alle APIs parallel abfragen
        try:
            api_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in api_results:
                if isinstance(result, Exception):
                    logger.error(f"API-Fehler: {result}")
                elif result:
                    results.extend(result if isinstance(result, list) else [result])
        
        except Exception as e:
            logger.error(f"Fehler bei parallelen API-Anfragen: {e}")
        
        # Nach Confidence-Score sortieren
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    async def _query_musicbrainz(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> List[MetadataResult]:
        """Fragt MusicBrainz-Datenbank ab."""
        results = []
        
        try:
            # Verschiedene Suchanfragen für bessere Ergebnisse
            search_queries = []
            
            # Basis-Suche
            search_queries.append(f'artist:"{artist}" AND recording:"{title}"')
            
            # Erweiterte Suche mit Album
            if album:
                search_queries.append(f'artist:"{artist}" AND recording:"{title}" AND release:"{album}"')
            
            # Suche mit Variationen
            artist_variations = extract_artist_variations(artist)
            title_variations = extract_title_variations(title)
            
            for art_var in artist_variations[:2]:  # Nur erste 2 Variationen
                for title_var in title_variations[:2]:
                    if art_var != artist or title_var != title:
                        search_queries.append(f'artist:"{art_var}" AND recording:"{title_var}"')
            
            for query in search_queries[:5]:  # Maximal 5 Queries
                try:
                    recordings = mb.search_recordings(
                        query=query, 
                        limit=10,
                        offset=0
                    )
                    
                    for recording in recordings['recording-list']:
                        result = self._parse_musicbrainz_recording(
                            recording, artist, title
                        )
                        if result and result.confidence >= 0.6:
                            results.append(result)
                    
                    # Pause zwischen Anfragen (MusicBrainz Rate Limiting)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"MusicBrainz Anfrage fehlgeschlagen: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"MusicBrainz Fehler: {e}")
        
        return results
    
    def _parse_musicbrainz_recording(
        self, 
        recording: Dict, 
        query_artist: str, 
        query_title: str
    ) -> Optional[MetadataResult]:
        """Parst MusicBrainz Recording-Daten."""
        try:
            mb_title = recording.get('title', '')
            mb_artist = ''
            mb_album = ''
            mb_year = None
            mb_id = recording.get('id', '')
            mb_genres = []
            
            # Künstler extrahieren
            if 'artist-credit' in recording:
                artists = []
                for credit in recording['artist-credit']:
                    if isinstance(credit, dict) and 'artist' in credit:
                        artists.append(credit['artist']['name'])
                    elif isinstance(credit, str):
                        artists.append(credit)
                mb_artist = ' & '.join(artists)
            
            # Album und Jahr extrahieren
            if 'release-list' in recording:
                releases = recording['release-list']
                if releases:
                    release = releases[0]  # Nehme erste Veröffentlichung
                    mb_album = release.get('title', '')
                    
                    # Jahr extrahieren
                    if 'date' in release:
                        year_str = release['date']
                        mb_year = extract_year_from_string(year_str)
            
            # Genres extrahieren (falls verfügbar)
            if 'tag-list' in recording:
                for tag in recording['tag-list']:
                    if tag.get('count', 0) > 0:
                        genre = clean_genre(tag.get('name', ''))
                        if genre and genre not in mb_genres:
                            mb_genres.append(genre)
            
            # Confidence-Score berechnen
            confidence = match_artist_title(
                query_artist, query_title, mb_artist, mb_title
            )
            
            return MetadataResult(
                source='musicbrainz',
                confidence=confidence,
                artist=mb_artist,
                title=mb_title,
                album=mb_album,
                year=mb_year,
                genres=mb_genres,
                musicbrainz_id=mb_id
            )
        
        except Exception as e:
            logger.warning(f"Fehler beim Parsen von MusicBrainz-Daten: {e}")
            return None
    
    async def _query_spotify(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> List[MetadataResult]:
        """Fragt Spotify Web API ab."""
        results = []
        
        if not self.spotify:
            return results
        
        try:
            # Verschiedene Suchstrings ausprobieren
            search_queries = [
                f'artist:"{artist}" track:"{title}"',
                f'"{artist}" "{title}"',
                f'{artist} {title}'
            ]
            
            if album:
                search_queries.insert(0, f'artist:"{artist}" track:"{title}" album:"{album}"')
            
            for query in search_queries:
                try:
                    search_results = self.spotify.search(
                        q=query, 
                        type='track', 
                        limit=10,
                        market='DE'  # Deutsche Markt-Daten
                    )
                    
                    tracks = search_results.get('tracks', {}).get('items', [])
                    
                    for track in tracks:
                        result = self._parse_spotify_track(track, artist, title)
                        if result and result.confidence >= 0.6:
                            results.append(result)
                  except Exception as e:
                    logger.warning(f"Spotify Suche fehlgeschlagen für '{query}': {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Spotify Fehler: {e}")
        
        return results
    
    def _parse_spotify_track(
        self, 
        track: Dict, 
        query_artist: str, 
        query_title: str
    ) -> Optional[MetadataResult]:
        """Parst Spotify Track-Daten."""
        try:
            sp_title = track.get('name', '')
            sp_artists = [artist['name'] for artist in track.get('artists', [])]
            sp_artist = ' & '.join(sp_artists)
            sp_album = track.get('album', {}).get('name', '')
            sp_year = None
            sp_id = track.get('id', '')
            sp_popularity = track.get('popularity', 0)
            sp_explicit = track.get('explicit', False)
            sp_duration = track.get('duration_ms', 0) // 1000  # Konvertiere zu Sekunden
            
            # Jahr extrahieren
            release_date = track.get('album', {}).get('release_date', '')
            if release_date:
                sp_year = extract_year_from_string(release_date)
            
            # Genres von Album abrufen (falls verfügbar)
            sp_genres = []
            album_genres = track.get('album', {}).get('genres', [])
            for genre in album_genres:
                clean_g = clean_genre(genre)
                if clean_g and clean_g not in sp_genres:
                    sp_genres.append(clean_g)
            
            # Zusätzliche Künstler-Informationen abrufen
            spotify_artist_followers = None
            spotify_monthly_listeners = None
            spotify_preview_url = track.get('preview_url', '')
            
            try:
                # Hauptkünstler-Informationen abrufen
                if track.get('artists') and len(track['artists']) > 0:
                    main_artist_id = track['artists'][0]['id']
                    artist_info = self.spotify.artist(main_artist_id)
                    
                    spotify_artist_followers = artist_info.get('followers', {}).get('total', 0)
                    # Hinweis: Monthly Listeners sind nicht über die öffentliche API verfügbar
                    # Wir können sie aber später über andere Endpunkte oder Schätzungen ergänzen
                    
            except Exception as e:
                logger.debug(f"Fehler beim Abrufen der Künstler-Details: {e}")
            
            # Confidence-Score berechnen
            confidence = match_artist_title(
                query_artist, query_title, sp_artist, sp_title
            )
            
            return MetadataResult(
                source='spotify',
                confidence=confidence,
                artist=sp_artist,
                title=sp_title,
                album=sp_album,
                year=sp_year,
                genres=sp_genres,
                duration=sp_duration,
                spotify_id=sp_id,
                popularity=sp_popularity,
                explicit=sp_explicit,
                spotify_artist_followers=spotify_artist_followers,
                spotify_preview_url=spotify_preview_url
            )
        
        except Exception as e:
            logger.warning(f"Fehler beim Parsen von Spotify-Daten: {e}")
            return None
    
    async def _query_lastfm(self, artist: str, title: str) -> List[MetadataResult]:
        """Fragt Last.fm API ab."""
        results = []
        
        if not self.lastfm_api_key:
            return results
        
        try:
            async with aiohttp.ClientSession() as session:
                # Track-Info abrufen
                track_url = 'http://ws.audioscrobbler.com/2.0/'
                track_params = {
                    'method': 'track.getInfo',
                    'api_key': self.lastfm_api_key,
                    'artist': artist,
                    'track': title,
                    'format': 'json'
                }
                
                async with session.get(track_url, params=track_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'track' in data:
                            result = self._parse_lastfm_track(
                                data['track'], artist, title
                            )
                            if result:
                                results.append(result)
        
        except Exception as e:
            logger.error(f"Last.fm Fehler: {e}")
        
        return results
    
    def _parse_lastfm_track(
        self, 
        track: Dict, 
        query_artist: str, 
        query_title: str
    ) -> Optional[MetadataResult]:
        """Parst Last.fm Track-Daten."""
        try:
            lf_title = track.get('name', '')
            lf_artist = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else str(track.get('artist', ''))
            lf_album = track.get('album', {}).get('title', '') if isinstance(track.get('album'), dict) else ''
            lf_url = track.get('url', '')
            lf_playcount = int(track.get('playcount', 0))
            lf_genres = []
            
            # Tags als Genres verwenden
            if 'toptags' in track and 'tag' in track['toptags']:
                tags = track['toptags']['tag']
                if isinstance(tags, list):
                    for tag in tags[:5]:  # Nur Top 5 Tags
                        genre = clean_genre(tag.get('name', ''))
                        if genre and genre not in lf_genres:
                            lf_genres.append(genre)
                elif isinstance(tags, dict):
                    genre = clean_genre(tags.get('name', ''))
                    if genre:
                        lf_genres.append(genre)
            
            # Confidence-Score berechnen
            confidence = match_artist_title(
                query_artist, query_title, lf_artist, lf_title
            )
            
            return MetadataResult(
                source='lastfm',
                confidence=confidence,
                artist=lf_artist,
                title=lf_title,
                album=lf_album,
                genres=lf_genres,
                lastfm_url=lf_url,
                popularity=min(lf_playcount // 1000, 100)  # Normalisiere auf 0-100
            )
        
        except Exception as e:
            logger.warning(f"Fehler beim Parsen von Last.fm-Daten: {e}")
            return None
    
    def merge_metadata_results(
        self, 
        results: List[MetadataResult], 
        min_confidence: float = 0.8
    ) -> Dict[str, Any]:
        """
        Führt mehrere MetadataResults zu einem konsolidierten Datensatz zusammen.
        
        Args:
            results: Liste von MetadataResult-Objekten
            min_confidence: Minimum Confidence für berücksichtigte Ergebnisse
            
        Returns:
            Konsolidiertes Metadaten-Dictionary
        """
        if not results:
            return {}
        
        # Nur Ergebnisse mit ausreichender Confidence verwenden
        filtered_results = [r for r in results if r.confidence >= min_confidence]
        
        if not filtered_results:
            # Falls keine Ergebnisse den Threshold erreichen, nehme das beste
            filtered_results = [max(results, key=lambda x: x.confidence)]
        
        merged = {}
        
        # Basis-Informationen vom besten Ergebnis
        best_result = filtered_results[0]
        merged.update({
            'artist': best_result.artist,
            'title': best_result.title,
            'album': best_result.album,
            'year': best_result.year,
            'duration': best_result.duration,
            'explicit': best_result.explicit,
            'primary_source': best_result.source,
            'confidence': best_result.confidence
        })
        
        # IDs sammeln
        ids = {}
        for result in filtered_results:
            if result.musicbrainz_id:
                ids['musicbrainz'] = result.musicbrainz_id
            if result.spotify_id:
                ids['spotify'] = result.spotify_id
            if result.lastfm_url:
                ids['lastfm'] = result.lastfm_url
        
        merged['external_ids'] = ids
        
        # Genres zusammenführen
        all_genres = []
        genre_counts = {}
        
        for result in filtered_results:
            for genre in result.genres:
                if genre not in genre_counts:
                    genre_counts[genre] = 0
                genre_counts[genre] += result.confidence
        
        # Top-Genres nach gewichteter Häufigkeit
        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        max_genres = self.config.get('genre_settings.max_genres', 3)
        merged['genres'] = [genre for genre, _ in sorted_genres[:max_genres]]
        
        # Popularitätsscore (Durchschnitt aller Quellen)
        popularity_scores = [r.popularity for r in filtered_results if r.popularity is not None]
        if popularity_scores:
            merged['popularity'] = sum(popularity_scores) // len(popularity_scores)
        
        return merged
    
    def get_api_status(self) -> Dict[str, bool]:
        """
        Gibt den Status aller konfigurierten APIs zurück.
        
        Returns:
            Dictionary mit API-Namen als Keys und Status als Values
        """
        return {
            'musicbrainz': True,  # MusicBrainz benötigt keine API-Keys
            'spotify': self.spotify is not None,
            'lastfm': self.lastfm_api_key is not None
        }
