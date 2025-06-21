"""
Tag Manager für MP3 Tagger

Verwaltet das sichere Lesen und Schreiben von ID3-Tags in MP3-Dateien.
Unterstützt Custom Tags für YouTube-URLs, Klickzahlen und andere Metadaten.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3NoHeaderError, TALB, TPE1, TIT2, TDRC, TCON, 
    TPE2, TRCK, TXXX, COMM, USLT
)

from .backup_manager import BackupManager
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS
from mutagen.id3 import TXXX, WXXX, COMM, APIC

from .config_manager import get_config

logger = logging.getLogger(__name__)


class TagManager:
    """Verwaltet ID3-Tags in MP3-Dateien."""
    
    def __init__(self, config=None):
        """Initialisiert den Tag Manager."""
        self.config = config or get_config()
        
        # Initialisiere modernen Backup-Manager
        self.backup_manager = BackupManager(self.config)
        
        # Legacy-Backup Einstellungen (für Fallback)
        self.backup_enabled = self.config.get('backup.auto_backup', True)
        self.backup_dir = Path(self.config.get('backup.directory', 'backups'))
        
        # Stelle sicher, dass Backup-Verzeichnis existiert
        if self.backup_enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def read_tags(self, file_path: Path) -> Dict[str, Any]:
        """
        Liest alle Tags aus einer MP3-Datei.
        
        Args:
            file_path: Pfad zur MP3-Datei
            
        Returns:
            Dictionary mit allen Tags
        """
        tags = {}
        
        try:
            audio_file = MP3(file_path)
            
            if audio_file.tags is None:
                return tags
            
            # Standard ID3v2 Tags
            tag_mappings = {
                'TIT2': 'title',
                'TPE1': 'artist',
                'TALB': 'album',
                'TPE2': 'albumartist',
                'TDRC': 'date',
                'TYER': 'year',
                'TCON': 'genre',
                'TRCK': 'track',
                'TPOS': 'disc',
                'TCOM': 'composer',
                'TPE3': 'conductor',
                'TIT1': 'contentgroup',
                'TIT3': 'subtitle',
                'TKEY': 'key',
                'TBPM': 'bpm',
                'TCOP': 'copyright',
                'TENC': 'encodedby',
                'TEXT': 'lyricist',
                'TLAN': 'language',
                'TMED': 'media',
                'TOAL': 'originalalbum',
                'TOFN': 'originalfilename',
                'TOLY': 'originallyricist',
                'TOPE': 'originalartist',
                'TOWN': 'fileowner',
                'TPE4': 'modifiedby',
                'TPUB': 'publisher',
                'TRDA': 'recordingdate',
                'TSRC': 'isrc',
                'TSSE': 'encodingsettings',
            }
            
            # Standard Tags extrahieren
            for tag_id, tag_name in tag_mappings.items():
                if tag_id in audio_file.tags:
                    tag_value = audio_file.tags[tag_id]
                    if hasattr(tag_value, 'text') and tag_value.text:
                        tags[tag_name] = str(tag_value.text[0])
            
            # TXXX Custom Text Tags
            custom_tags = self._extract_custom_text_tags(audio_file.tags)
            tags.update(custom_tags)
            
            # WXXX Custom URL Tags
            url_tags = self._extract_custom_url_tags(audio_file.tags)
            tags.update(url_tags)
            
            # COMM Comment Tags
            comment_tags = self._extract_comment_tags(audio_file.tags)
            tags.update(comment_tags)
            
            # Spezielle Tags für unsere Anwendung
            mp3_tagger_tags = self._extract_mp3_tagger_tags(audio_file.tags)
            tags.update(mp3_tagger_tags)
            
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Tags von {file_path}: {e}")
        
        return tags
    
    def _extract_custom_text_tags(self, id3_tags) -> Dict[str, str]:
        """Extrahiert TXXX (Custom Text) Tags."""
        custom_tags = {}
        
        for tag in id3_tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'TXXX':
                key = f"custom_text_{tag.desc.lower().replace(' ', '_')}"
                if hasattr(tag, 'text') and tag.text:
                    custom_tags[key] = str(tag.text[0])
        
        return custom_tags
    
    def _extract_custom_url_tags(self, id3_tags) -> Dict[str, str]:
        """Extrahiert WXXX (Custom URL) Tags."""
        url_tags = {}
        
        for tag in id3_tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'WXXX':
                key = f"custom_url_{tag.desc.lower().replace(' ', '_')}"
                if hasattr(tag, 'url'):
                    url_tags[key] = str(tag.url)
        
        return url_tags
    
    def _extract_comment_tags(self, id3_tags) -> Dict[str, str]:
        """Extrahiert COMM (Comment) Tags."""
        comment_tags = {}
        
        for tag in id3_tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'COMM':
                if tag.desc:
                    key = f"comment_{tag.desc.lower().replace(' ', '_')}"
                else:
                    key = "comment"
                
                if hasattr(tag, 'text') and tag.text:
                    comment_tags[key] = str(tag.text[0])
        
        return comment_tags
    
    def _extract_mp3_tagger_tags(self, id3_tags) -> Dict[str, Any]:
        """Extrahiert spezielle MP3-Tagger Tags."""
        mp3_tags = {}
        
        # YouTube-spezifische Tags
        youtube_tags = [
            'YOUTUBE_URL', 'YOUTUBE_VIDEO_ID', 'YOUTUBE_VIEWS', 
            'YOUTUBE_LIKES', 'YOUTUBE_CHANNEL', 'YOUTUBE_PUBLISHED'
        ]
        
        # Spotify-spezifische Tags
        spotify_tags = [
            'SPOTIFY_ID', 'SPOTIFY_URL', 'SPOTIFY_POPULARITY'
        ]
        
        # Allgemeine Tags
        general_tags = [
            'POPULARITY_SCORE', 'CONFIDENCE_SCORE', 'LAST_UPDATED',
            'MUSICBRAINZ_ID', 'LASTFM_URL', 'EXTERNAL_IDS'
        ]
        
        all_special_tags = youtube_tags + spotify_tags + general_tags
        
        for tag in id3_tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'TXXX':
                if tag.desc in all_special_tags:
                    key = tag.desc.lower()
                    if hasattr(tag, 'text') and tag.text:
                        value = str(tag.text[0])
                        
                        # JSON-Dekodierung für komplexe Daten
                        if key == 'external_ids':
                            try:
                                mp3_tags[key] = json.loads(value)
                            except:
                                mp3_tags[key] = value
                        # Numerische Werte konvertieren
                        elif key in ['youtube_views', 'youtube_likes', 'spotify_popularity', 'popularity_score']:
                            try:
                                mp3_tags[key] = int(value)
                            except:
                                mp3_tags[key] = value                        # Datum konvertieren
                        elif key in ['youtube_published', 'last_updated']:
                            try:
                                mp3_tags[key] = datetime.fromisoformat(value)
                            except:
                                mp3_tags[key] = value
                        else:
                            mp3_tags[key] = value
        
        return mp3_tags
    
    def write_tags(
        self, 
        file_path: Path, 
        tags: Dict[str, Any], 
        create_backup: bool = True
    ) -> bool:
        """
        Schreibt Tags in eine MP3-Datei mit modernem Backup-System.
        
        Args:
            file_path: Pfad zur MP3-Datei
            tags: Dictionary mit zu schreibenden Tags
            create_backup: Ob ein Backup erstellt werden soll
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        backup_created = False
        
        try:
            # Modernes Backup erstellen
            if create_backup and self.backup_enabled:
                current_tags = self.read_tags(file_path)
                backup_created = self.backup_manager.create_backup(file_path, current_tags)
                if not backup_created:
                    logger.warning(f"Backup-Erstellung fehlgeschlagen für {file_path}")
            
            # MP3-Datei laden
            audio_file = MP3(file_path)
            
            # ID3-Tags initialisieren falls nicht vorhanden
            if audio_file.tags is None:
                audio_file.add_tags()
            
            # Tags schreiben
            self._write_standard_tags(audio_file, tags)
            self._write_custom_tags(audio_file, tags)
            self._write_mp3_tagger_tags(audio_file, tags)
            
            # Metadaten zur Nachverfolgung hinzufügen
            self._add_metadata_tracking(audio_file, tags)
            
            # Datei speichern
            audio_file.save()
            
            # Changelog finalisieren (bei entsprechender Strategie)
            if backup_created:
                self.backup_manager.finalize_changelog(file_path, tags)
                self.backup_manager.commit_transaction(file_path)
            
            logger.info(f"Tags erfolgreich geschrieben: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Schreiben der Tags für {file_path}: {e}")
            
            # Rollback bei Fehler
            if backup_created:
                self.backup_manager.rollback_transaction(file_path)
                logger.info(f"Backup-Rollback ausgeführt für {file_path}")
            
            return False
    
    def _write_standard_tags(self, audio_file: MP3, tags: Dict[str, Any]) -> None:
        """Schreibt Standard ID3v2 Tags."""
        standard_mappings = {
            'title': TIT2,
            'artist': TPE1,
            'album': TALB,
            'albumartist': TPE2,
            'date': TDRC,
            'year': TDRC,  # Fallback für Jahr
            'genre': TCON,
            'track': TRCK,
            'disc': TPOS,
        }
        
        for tag_name, tag_class in standard_mappings.items():
            if tag_name in tags and tags[tag_name]:
                value = str(tags[tag_name])
                
                # Spezielle Behandlung für Genre (kann Liste sein)
                if tag_name == 'genre' and isinstance(tags[tag_name], list):
                    value = '; '.join(tags[tag_name])
                
                # Spezielle Behandlung für Track (kann "1/12" Format haben)
                elif tag_name == 'track' and '/' not in value:
                    # Versuche total_tracks zu finden
                    if 'total_tracks' in tags:
                        value = f"{value}/{tags['total_tracks']}"
                
                audio_file.tags[tag_class.__name__] = tag_class(encoding=3, text=value)
    
    def _write_custom_tags(self, audio_file: MP3, tags: Dict[str, Any]) -> None:
        """Schreibt benutzerdefinierte Tags."""
        custom_mappings = self.config.get('tag_settings.custom_tags', {})
        
        for tag_name, tag_mapping in custom_mappings.items():
            if tag_name in tags and tags[tag_name]:
                value = str(tags[tag_name])
                
                if tag_mapping.startswith('TXXX:'):
                    # Custom Text Tag
                    desc = tag_mapping[5:]  # Entferne "TXXX:" Prefix
                    audio_file.tags[f"TXXX:{desc}"] = TXXX(
                        encoding=3, desc=desc, text=value
                    )
                elif tag_mapping.startswith('WXXX:'):
                    # Custom URL Tag
                    desc = tag_mapping[5:]  # Entferne "WXXX:" Prefix
                    audio_file.tags[f"WXXX:{desc}"] = WXXX(
                        encoding=3, desc=desc, url=value
                    )
    
    def _write_mp3_tagger_tags(self, audio_file: MP3, tags: Dict[str, Any]) -> None:
        """Schreibt MP3-Tagger spezifische Tags."""
        
        # YouTube Tags
        youtube_mappings = {
            'youtube_url': 'YOUTUBE_URL',
            'youtube_video_id': 'YOUTUBE_VIDEO_ID', 
            'youtube_views': 'YOUTUBE_VIEWS',
            'youtube_likes': 'YOUTUBE_LIKES',
            'youtube_channel': 'YOUTUBE_CHANNEL',
            'youtube_published': 'YOUTUBE_PUBLISHED'
        }
        
        # Spotify Tags
        spotify_mappings = {
            'spotify_id': 'SPOTIFY_ID',
            'spotify_url': 'SPOTIFY_URL',
            'spotify_popularity': 'SPOTIFY_POPULARITY'
        }
        
        # Allgemeine Tags
        general_mappings = {
            'popularity_score': 'POPULARITY_SCORE',
            'confidence_score': 'CONFIDENCE_SCORE',
            'musicbrainz_id': 'MUSICBRAINZ_ID',
            'lastfm_url': 'LASTFM_URL',
            'external_ids': 'EXTERNAL_IDS'
        }
        
        all_mappings = {**youtube_mappings, **spotify_mappings, **general_mappings}
        
        for tag_name, txxx_desc in all_mappings.items():
            if tag_name in tags and tags[tag_name] is not None:
                value = tags[tag_name]
                
                # Spezielle Behandlung für verschiedene Datentypen
                if isinstance(value, dict):
                    # JSON-Kodierung für komplexe Daten
                    value_str = json.dumps(value, ensure_ascii=False)
                elif isinstance(value, datetime):
                    # ISO-Format für Datum/Zeit
                    value_str = value.isoformat()
                elif isinstance(value, list):
                    # Komma-getrennt für Listen
                    value_str = ', '.join(str(v) for v in value)
                else:
                    value_str = str(value)
                
                audio_file.tags[f"TXXX:{txxx_desc}"] = TXXX(
                    encoding=3, desc=txxx_desc, text=value_str
                )
    
    def _add_metadata_tracking(self, audio_file: MP3, tags: Dict[str, Any]) -> None:
        """Fügt Metadaten zur Nachverfolgung hinzu."""
        # Zeitstempel der letzten Aktualisierung
        audio_file.tags["TXXX:LAST_UPDATED"] = TXXX(            encoding=3, 
            desc="LAST_UPDATED", 
            text=datetime.now().isoformat()
        )
        
        # Version des MP3-Taggers
        audio_file.tags["TXXX:MP3_TAGGER_VERSION"] = TXXX(
            encoding=3,
            desc="MP3_TAGGER_VERSION",
            text="1.0.0"
        )
        
        # Quellen der Metadaten
        if 'primary_source' in tags:
            audio_file.tags["TXXX:METADATA_SOURCE"] = TXXX(
                encoding=3,
                desc="METADATA_SOURCE",
                text=str(tags['primary_source'])
            )
    
    def restore_from_backup(self, file_path: Path, 
                           backup_timestamp: Optional[str] = None) -> bool:
        """
        Stellt eine Datei aus dem Backup wieder her.
        
        Args:
            file_path: Pfad zur wiederherzustellenden Datei
            backup_timestamp: Spezifischer Backup-Zeitstempel (None = neuestes)
            
        Returns:
            True bei Erfolg
        """
        return self.backup_manager.restore_from_backup(file_path, backup_timestamp)
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Gibt Backup-Statistiken zurück."""
        return self.backup_manager.get_backup_stats()
    
    def cleanup_old_backups(self) -> int:
        """Entfernt alte Backups und gibt die Anzahl zurück."""
        return self.backup_manager.cleanup_old_backups()
    
    def is_tag_protected(self, tag_name: str) -> bool:
        """
        Prüft ob ein Tag geschützt ist.
        
        Args:
            tag_name: Name des Tags
            
        Returns:
            True wenn der Tag geschützt ist
        """
        return self.config.is_tag_protected(tag_name)
    
    def is_tag_processable(self, tag_name: str) -> bool:
        """
        Prüft ob ein Tag verarbeitet werden kann.
        
        Args:
            tag_name: Name des Tags
            
        Returns:
            True wenn der Tag verarbeitet werden kann
        """
        return self.config.is_tag_processable(tag_name)
    
    def get_tag_conflicts(
        self, 
        existing_tags: Dict[str, Any], 
        new_tags: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Ermittelt Konflikte zwischen vorhandenen und neuen Tags.
        
        Args:
            existing_tags: Vorhandene Tags
            new_tags: Neue Tags
            
        Returns:
            Dictionary mit Konflikten
        """
        conflicts = {}
        
        for tag_name, new_value in new_tags.items():
            if tag_name in existing_tags:
                existing_value = existing_tags[tag_name]
                
                # Keine Konflikte für geschützte Tags
                if self.is_tag_protected(tag_name):
                    continue
                
                # Verschiedene Werte = Konflikt
                if str(existing_value).strip() != str(new_value).strip():
                    conflicts[tag_name] = {
                        'existing': existing_value,
                        'new': new_value,
                        'protected': self.is_tag_protected(tag_name),
                        'auto_update': self.config.is_auto_update_tag(tag_name)
                    }
        
        return conflicts
    
    def merge_tags(
        self, 
        existing_tags: Dict[str, Any], 
        new_tags: Dict[str, Any], 
        conflict_resolution: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Führt vorhandene und neue Tags zusammen.
        
        Args:
            existing_tags: Vorhandene Tags
            new_tags: Neue Tags
            conflict_resolution: Auflösung für Konflikte {'tag_name': 'keep_existing'|'use_new'}
            
        Returns:
            Zusammengeführte Tags
        """
        merged = existing_tags.copy()
        conflict_resolution = conflict_resolution or {}
        
        for tag_name, new_value in new_tags.items():
            # Geschützte Tags nicht überschreiben
            if self.is_tag_protected(tag_name):
                continue
            
            # Neuer Tag ohne Konflikt
            if tag_name not in existing_tags:
                merged[tag_name] = new_value
                continue
            
            # Konflikt-Auflösung
            if tag_name in conflict_resolution:
                if conflict_resolution[tag_name] == 'use_new':
                    merged[tag_name] = new_value
                # 'keep_existing' ist Default - nichts tun
                continue
            
            # Auto-Update Tags automatisch überschreiben
            if self.config.is_auto_update_tag(tag_name):
                merged[tag_name] = new_value
                continue
            
            # Sonst vorhandenen Wert behalten
        
        return merged
    
    def cleanup_old_backups(self, max_age_days: int = None) -> int:
        """
        Bereinigt alte Backup-Dateien.
        
        Args:
            max_age_days: Maximales Alter in Tagen (None = aus Konfiguration)
            
        Returns:
            Anzahl gelöschter Dateien
        """
        if max_age_days is None:
            max_age_days = self.config.get('backup.max_age_days', 90)
        
        deleted_count = 0
        cutoff_date = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        
        try:
            for backup_file in self.backup_dir.glob('*.mp3'):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Altes Backup gelöscht: {backup_file}")
        
        except Exception as e:
            logger.error(f"Fehler beim Bereinigen der Backups: {e}")
        
        return deleted_count
    
    def get_all_custom_tags(self, file_path: Path) -> Dict[str, str]:
        """
        Gibt alle benutzerdefinierten Tags einer Datei zurück.
        
        Args:
            file_path: Pfad zur MP3-Datei
            
        Returns:
            Dictionary mit allen TXXX und WXXX Tags
        """
        custom_tags = {}
        
        try:
            audio_file = MP3(file_path)
            
            if audio_file.tags is None:
                return custom_tags
            
            # TXXX Tags
            for tag in audio_file.tags.values():
                if hasattr(tag, 'desc') and tag.FrameID == 'TXXX':
                    if hasattr(tag, 'text') and tag.text:
                        custom_tags[f"TXXX:{tag.desc}"] = str(tag.text[0])
            
            # WXXX Tags
            for tag in audio_file.tags.values():
                if hasattr(tag, 'desc') and tag.FrameID == 'WXXX':
                    if hasattr(tag, 'url'):
                        custom_tags[f"WXXX:{tag.desc}"] = str(tag.url)
        
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Custom Tags von {file_path}: {e}")
        
        return custom_tags
