"""
YouTube Handler für MP3 Tagger

Sucht YouTube-Videos für Songs und ruft Statistiken ab.
Unterstützt mehrere Video-Dienste für umfassende Abdeckung.
"""

import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config_manager import get_config
from .utils.string_matching import calculate_similarity, normalize_string

logger = logging.getLogger(__name__)


@dataclass
class VideoResult:
    """Ergebnis einer Video-Suche."""
    platform: str
    video_id: str
    url: str
    title: str
    channel: str
    view_count: int
    like_count: Optional[int] = None
    duration: Optional[str] = None
    published_date: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    confidence: float = 0.0
    is_official: bool = False
    is_music_video: bool = False


class YouTubeHandler:
    """Verwaltet YouTube-Integrationen und Video-Suchen."""
    
    def __init__(self):
        """Initialisiert den YouTube Handler."""
        self.config = get_config()
        self.youtube_api_key = self.config.get_api_key('youtube_api_key')
        self.youtube = None
        
        if self.youtube_api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
                logger.info("YouTube API erfolgreich initialisiert")
            except Exception as e:
                logger.error(f"YouTube API Initialisierung fehlgeschlagen: {e}")
        else:
            logger.info("YouTube API-Key nicht konfiguriert")
    
    async def find_videos(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> List[VideoResult]:
        """
        Sucht Videos für einen Song auf verschiedenen Plattformen.
        
        Args:
            artist: Künstlername
            title: Songtitel
            album: Album (optional)
            
        Returns:
            Liste von VideoResult-Objekten sortiert nach Relevanz
        """
        all_results = []
        
        # YouTube-Suche
        if self.youtube:
            youtube_results = await self._search_youtube(artist, title, album)
            all_results.extend(youtube_results)
        
        # Weitere Plattformen könnten hier hinzugefügt werden
        # - Vimeo API
        # - SoundCloud API
        # - etc.
        
        # Nach Confidence und View Count sortieren
        all_results.sort(key=lambda x: (x.confidence, x.view_count), reverse=True)
        
        return all_results
    
    async def _search_youtube(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> List[VideoResult]:
        """Sucht Videos auf YouTube."""
        results = []
        
        if not self.youtube:
            return results
        
        try:
            # Verschiedene Suchstrings für bessere Ergebnisse
            search_formats = self.config.get('youtube_settings.search_formats', [
                "{artist} - {title} official",
                "{artist} {title} official music video",
                "{artist} {title}",
                "{title} {artist}"
            ])
            
            search_queries = []
            for fmt in search_formats:
                query = fmt.format(artist=artist, title=title)
                search_queries.append(query)
            
            # Album-spezifische Suchen hinzufügen
            if album:
                search_queries.insert(0, f"{artist} {title} {album}")
                search_queries.insert(1, f"{artist} - {title} {album} official")
            
            max_results_per_query = self.config.get('matching_settings.max_results_per_query', 10)
            
            for query in search_queries[:5]:  # Maximal 5 verschiedene Suchen
                try:
                    # YouTube Search API
                    search_response = self.youtube.search().list(
                        q=query,
                        part='id,snippet',
                        type='video',
                        maxResults=max_results_per_query,
                        order='relevance',
                        videoCategoryId='10',  # Musik-Kategorie
                        regionCode='DE'  # Deutsche Region
                    ).execute()
                    
                    video_ids = []
                    video_data = {}
                    
                    for item in search_response.get('items', []):
                        video_id = item['id']['videoId']
                        video_ids.append(video_id)
                        video_data[video_id] = item['snippet']
                    
                    if video_ids:
                        # Video-Details und Statistiken abrufen
                        videos_response = self.youtube.videos().list(
                            part='statistics,contentDetails,snippet',
                            id=','.join(video_ids)
                        ).execute()
                        
                        for video in videos_response.get('items', []):
                            result = self._parse_youtube_video(
                                video, video_data.get(video['id'], {}), artist, title
                            )
                            if result:
                                results.append(result)
                
                except HttpError as e:
                    logger.error(f"YouTube API Fehler für '{query}': {e}")
                    continue
                except Exception as e:
                    logger.warning(f"YouTube Suche fehlgeschlagen für '{query}': {e}")
                    continue
                
                # Rate Limiting beachten
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"YouTube Handler Fehler: {e}")
        
        return results
    
    def _parse_youtube_video(
        self, 
        video: Dict, 
        snippet: Dict, 
        query_artist: str, 
        query_title: str
    ) -> Optional[VideoResult]:
        """Parst YouTube Video-Daten."""
        try:
            video_id = video['id']
            video_snippet = video.get('snippet', snippet)
            statistics = video.get('statistics', {})
            content_details = video.get('contentDetails', {})
            
            yt_title = video_snippet.get('title', '')
            yt_channel = video_snippet.get('channelTitle', '')
            yt_description = video_snippet.get('description', '')
            
            # Statistiken
            view_count = int(statistics.get('viewCount', 0))
            like_count = int(statistics.get('likeCount', 0)) if 'likeCount' in statistics else None
            
            # Mindest-View-Count prüfen
            min_view_count = self.config.get('youtube_settings.min_view_count', 1000)
            if view_count < min_view_count:
                return None
            
            # Dauer
            duration = content_details.get('duration', '')
            
            # Veröffentlichungsdatum
            published_at = video_snippet.get('publishedAt', '')
            published_date = None
            if published_at:
                try:
                    published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except:
                    pass
            
            # Thumbnail
            thumbnails = video_snippet.get('thumbnails', {})
            thumbnail_url = None
            if 'maxres' in thumbnails:
                thumbnail_url = thumbnails['maxres']['url']
            elif 'high' in thumbnails:
                thumbnail_url = thumbnails['high']['url']
            elif 'medium' in thumbnails:
                thumbnail_url = thumbnails['medium']['url']
            
            # URL erstellen
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Confidence-Score berechnen
            confidence = self._calculate_video_confidence(
                yt_title, yt_channel, yt_description, query_artist, query_title
            )
            
            # Offizielle Indikatoren prüfen
            is_official = self._is_official_video(yt_title, yt_channel, yt_description)
            is_music_video = self._is_music_video(yt_title, yt_description)
            
            return VideoResult(
                platform='youtube',
                video_id=video_id,
                url=url,
                title=yt_title,
                channel=yt_channel,
                view_count=view_count,
                like_count=like_count,
                duration=duration,
                published_date=published_date,
                thumbnail_url=thumbnail_url,
                description=yt_description[:500] if yt_description else None,  # Kürzen
                confidence=confidence,
                is_official=is_official,
                is_music_video=is_music_video
            )
        
        except Exception as e:
            logger.warning(f"Fehler beim Parsen von YouTube-Video: {e}")
            return None
    
    def _calculate_video_confidence(
        self, 
        video_title: str, 
        channel: str, 
        description: str, 
        query_artist: str, 
        query_title: str
    ) -> float:
        """Berechnet Confidence-Score für Video-Match."""
        confidence = 0.0
        
        # Titel-Ähnlichkeit (50% Gewichtung)
        title_similarity = calculate_similarity(
            f"{query_artist} {query_title}", 
            video_title
        )
        confidence += title_similarity * 0.5
        
        # Künstler im Video-Titel (20% Gewichtung)
        if normalize_string(query_artist) in normalize_string(video_title):
            confidence += 0.2
        
        # Song-Titel im Video-Titel (20% Gewichtung)
        if normalize_string(query_title) in normalize_string(video_title):
            confidence += 0.2
        
        # Künstler im Kanal-Namen (10% Gewichtung)
        channel_similarity = calculate_similarity(query_artist, channel)
        confidence += channel_similarity * 0.1
        
        # Bonus für offizielle Indikatoren
        official_indicators = [
            'official', 'vevo', 'records', 'music', 'entertainment'
        ]
        
        for indicator in official_indicators:
            if indicator in normalize_string(channel) or indicator in normalize_string(video_title):
                confidence += 0.05
                break
        
        # Malus für problematische Inhalte
        blacklist_terms = self.config.get('youtube_settings.channel_blacklist', [])
        for term in blacklist_terms:
            if term in normalize_string(video_title) or term in normalize_string(channel):
                confidence -= 0.2
                break
        
        return max(0.0, min(1.0, confidence))
    
    def _is_official_video(self, title: str, channel: str, description: str) -> bool:
        """Prüft ob es sich um ein offizielles Video handelt."""
        official_indicators = [
            'vevo', 'records', 'official', 'entertainment', 'music'
        ]
        
        text_to_check = f"{title} {channel} {description}".lower()
        
        return any(indicator in text_to_check for indicator in official_indicators)
    
    def _is_music_video(self, title: str, description: str) -> bool:
        """Prüft ob es sich um ein Musik-Video handelt."""
        music_video_indicators = [
            'music video', 'official video', 'mv', 'clip', 'videoclip'
        ]
        
        text_to_check = f"{title} {description}".lower()
        
        return any(indicator in text_to_check for indicator in music_video_indicators)
    
    async def get_video_details(self, video_id: str, platform: str = 'youtube') -> Optional[VideoResult]:
        """
        Ruft aktuelle Details für ein spezifisches Video ab.
        
        Args:
            video_id: Video-ID
            platform: Plattform (derzeit nur 'youtube')
            
        Returns:
            VideoResult mit aktuellen Daten oder None
        """
        if platform == 'youtube' and self.youtube:
            return await self._get_youtube_video_details(video_id)
        
        return None
    
    async def _get_youtube_video_details(self, video_id: str) -> Optional[VideoResult]:
        """Ruft Details für ein YouTube-Video ab."""
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()
            
            items = response.get('items', [])
            if not items:
                return None
            
            video = items[0]
            
            return self._parse_youtube_video(video, {}, '', '')
        
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von YouTube-Video {video_id}: {e}")
            return None
    
    def extract_video_id_from_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrahiert Video-ID und Plattform aus einer URL.
        
        Args:
            url: Video-URL
            
        Returns:
            Tuple aus (video_id, platform) oder (None, None)
        """
        # YouTube URL-Patterns
        youtube_patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), 'youtube'
        
        # Weitere Plattformen könnten hier hinzugefügt werden
        
        return None, None
    
    def get_embed_url(self, video_id: str, platform: str = 'youtube') -> Optional[str]:
        """
        Erstellt Embed-URL für ein Video.
        
        Args:
            video_id: Video-ID
            platform: Plattform
            
        Returns:
            Embed-URL oder None
        """
        if platform == 'youtube':
            return f"https://www.youtube.com/embed/{video_id}"
        
        return None
    
    def format_view_count(self, count: int) -> str:
        """
        Formatiert View-Count für benutzerfreundliche Anzeige.
        
        Args:
            count: Anzahl Views
            
        Returns:
            Formatierter String (z.B. "1.2M", "456K")
        """
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        else:
            return str(count)
    
    def is_api_available(self) -> bool:
        """
        Prüft ob die YouTube API verfügbar ist.
        
        Returns:
            True wenn API konfiguriert und verfügbar ist
        """
        return self.youtube is not None


class MultiPlatformVideoHandler:
    """Erweiterte Klasse für mehrere Video-Plattformen."""
    
    def __init__(self):
        """Initialisiert Handler für mehrere Plattformen."""
        self.youtube_handler = YouTubeHandler()
        # Weitere Handler könnten hier hinzugefügt werden
    
    async def find_all_videos(
        self, 
        artist: str, 
        title: str, 
        album: Optional[str] = None
    ) -> Dict[str, List[VideoResult]]:
        """
        Sucht Videos auf allen verfügbaren Plattformen.
        
        Args:
            artist: Künstlername
            title: Songtitel
            album: Album (optional)
            
        Returns:
            Dictionary mit Plattform als Key und VideoResult-Liste als Value
        """
        results = {}
        
        # YouTube
        if self.youtube_handler.is_api_available():
            youtube_results = await self.youtube_handler.find_videos(artist, title, album)
            if youtube_results:
                results['youtube'] = youtube_results
        
        # Weitere Plattformen...
        
        return results
    
    def get_best_video(
        self, 
        platform_results: Dict[str, List[VideoResult]], 
        prefer_official: bool = True
    ) -> Optional[VideoResult]:
        """
        Wählt das beste Video aus allen Plattformen aus.
        
        Args:
            platform_results: Ergebnisse aller Plattformen
            prefer_official: Bevorzuge offizielle Videos
            
        Returns:
            Bestes VideoResult oder None
        """
        all_videos = []
        
        for platform, videos in platform_results.items():
            all_videos.extend(videos)
        
        if not all_videos:
            return None
        
        # Sortierung: Erst offizielle Videos, dann nach Confidence und Views
        def sort_key(video):
            official_bonus = 1.0 if video.is_official and prefer_official else 0.0
            music_video_bonus = 0.5 if video.is_music_video else 0.0
            view_score = min(video.view_count / 1_000_000, 100) / 100  # Normalisiert auf 0-1
            
            return official_bonus + video.confidence + music_video_bonus + (view_score * 0.1)
        
        sorted_videos = sorted(all_videos, key=sort_key, reverse=True)
        
        return sorted_videos[0]
