"""
File Scanner für MP3 Tagger

Scannt Verzeichnisse nach MP3-Dateien und extrahiert vorhandene Metadaten.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Mp3FileInfo:
    """Informationen über eine MP3-Datei."""
    file_path: Path
    file_size: int
    duration: float
    bitrate: int
    sample_rate: int
    existing_tags: Dict[str, Any]
    parsed_artist: Optional[str] = None
    parsed_title: Optional[str] = None
    confidence: float = 0.0


class FileScanner:
    """Scannt Verzeichnisse nach MP3-Dateien und extrahiert Metadaten."""
    
    def __init__(self):
        """Initialisiert den FileScanner."""
        self.supported_extensions = ['.mp3']
        self.filename_patterns = [
            # Künstler - Titel.mp3
            r'^(.+?)\s*-\s*(.+?)\.mp3$',
            # Künstler_Titel.mp3
            r'^(.+?)_(.+?)\.mp3$',
            # Titel (Künstler).mp3
            r'^(.+?)\s*\((.+?)\)\.mp3$',
            # Track Number - Künstler - Titel.mp3
            r'^\d+\s*-\s*(.+?)\s*-\s*(.+?)\.mp3$',
            # Track Number. Künstler - Titel.mp3
            r'^\d+\.\s*(.+?)\s*-\s*(.+?)\.mp3$',
        ]
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[Mp3FileInfo]:
        """
        Scannt ein Verzeichnis nach MP3-Dateien.
        
        Args:
            directory: Zu scannendes Verzeichnis
            recursive: Ob Unterverzeichnisse gescannt werden sollen
            
        Returns:
            Liste von Mp3FileInfo-Objekten
            
        Raises:
            FileNotFoundError: Wenn das Verzeichnis nicht existiert
        """
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise FileNotFoundError(f"Verzeichnis nicht gefunden: {directory}")
        
        if not directory_path.is_dir():
            raise NotADirectoryError(f"Pfad ist kein Verzeichnis: {directory}")
        
        logger.info(f"Scanne Verzeichnis: {directory} (recursive: {recursive})")
        
        mp3_files = []
        
        if recursive:
            # Rekursiv alle MP3-Dateien finden
            for file_path in directory_path.rglob("*.mp3"):
                if self._is_valid_mp3_file(file_path):
                    mp3_info = self._process_mp3_file(file_path)
                    if mp3_info:
                        mp3_files.append(mp3_info)
        else:
            # Nur im aktuellen Verzeichnis suchen
            for file_path in directory_path.glob("*.mp3"):
                if self._is_valid_mp3_file(file_path):
                    mp3_info = self._process_mp3_file(file_path)
                    if mp3_info:
                        mp3_files.append(mp3_info)
        
        logger.info(f"Gefunden: {len(mp3_files)} MP3-Dateien")
        return mp3_files
    
    def scan_single_file(self, file_path: str) -> Optional[Mp3FileInfo]:
        """
        Scannt eine einzelne MP3-Datei.
        
        Args:
            file_path: Pfad zur MP3-Datei
            
        Returns:
            Mp3FileInfo-Objekt oder None bei Fehlern
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Datei nicht gefunden: {file_path}")
            return None
        
        if not self._is_valid_mp3_file(path):
            logger.error(f"Keine gültige MP3-Datei: {file_path}")
            return None
        
        return self._process_mp3_file(path)
    
    def _is_valid_mp3_file(self, file_path: Path) -> bool:
        """
        Prüft, ob eine Datei eine gültige MP3-Datei ist.
        
        Args:
            file_path: Pfad zur Datei
            
        Returns:
            True wenn die Datei eine gültige MP3-Datei ist
        """
        # Dateierweiterung prüfen
        if file_path.suffix.lower() not in self.supported_extensions:
            return False
        
        # Dateigröße prüfen (Mindestgröße 1KB)
        try:
            if file_path.stat().st_size < 1024:
                logger.warning(f"Datei zu klein: {file_path}")
                return False
        except OSError:
            logger.error(f"Fehler beim Zugriff auf Datei: {file_path}")
            return False
        
        # Mit Mutagen prüfen, ob es eine gültige MP3-Datei ist
        try:
            audio_file = MutagenFile(file_path)
            return audio_file is not None and hasattr(audio_file, 'info')
        except Exception as e:
            logger.warning(f"Ungültige MP3-Datei {file_path}: {e}")
            return False
    
    def _process_mp3_file(self, file_path: Path) -> Optional[Mp3FileInfo]:
        """
        Verarbeitet eine MP3-Datei und extrahiert alle Informationen.
        
        Args:
            file_path: Pfad zur MP3-Datei
            
        Returns:
            Mp3FileInfo-Objekt oder None bei Fehlern
        """
        try:
            # Datei-Statistiken
            stat = file_path.stat()
            file_size = stat.st_size
            
            # Audio-Informationen laden
            audio_file = MP3(file_path)
            
            # Technische Informationen
            duration = audio_file.info.length
            bitrate = audio_file.info.bitrate
            sample_rate = audio_file.info.sample_rate
            
            # Vorhandene Tags extrahieren
            existing_tags = self._extract_existing_tags(audio_file)
            
            # Dateiname parsen
            parsed_artist, parsed_title, confidence = self._parse_filename(file_path.name)
            
            mp3_info = Mp3FileInfo(
                file_path=file_path,
                file_size=file_size,
                duration=duration,
                bitrate=bitrate,
                sample_rate=sample_rate,
                existing_tags=existing_tags,
                parsed_artist=parsed_artist,
                parsed_title=parsed_title,
                confidence=confidence
            )
            
            logger.debug(f"Verarbeitet: {file_path.name} - {parsed_artist} - {parsed_title}")
            return mp3_info
            
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von {file_path}: {e}")
            return None
    
    def _extract_existing_tags(self, audio_file: MP3) -> Dict[str, Any]:
        """
        Extrahiert alle vorhandenen ID3-Tags aus einer MP3-Datei.
        
        Args:
            audio_file: MP3-Objekt von Mutagen
            
        Returns:
            Dictionary mit vorhandenen Tags
        """
        tags = {}
        
        if audio_file.tags is None:
            return tags
        
        # Standard ID3v2 Tags
        tag_mappings = {
            'TPE1': 'artist',
            'TIT2': 'title',
            'TALB': 'album',
            'TPE2': 'albumartist',
            'TDRC': 'date',
            'TYER': 'year',
            'TCON': 'genre',
            'TRCK': 'track',
            'TPOS': 'disc',
            'COMM': 'comment',
            'TPE3': 'conductor',
            'TCOM': 'composer',
            'TIT1': 'contentgroup',
            'TIT3': 'subtitle',
            'TKEY': 'key',
            'TBPM': 'bpm',
            'TCOP': 'copyright',
            'TENC': 'encodedby',
            'TEXT': 'lyricist',
            'TFLT': 'filetype',
            'TIME': 'time',
            'TIT1': 'contentgroup',
            'TLAN': 'language',
            'TLEN': 'length',
            'TMED': 'media',
            'TOAL': 'originalalbum',
            'TOFN': 'originalfilename',
            'TOLY': 'originallyricist',
            'TOPE': 'originalartist',
            'TOWN': 'fileowner',
            'TPE4': 'modifiedby',
            'TPUB': 'publisher',
            'TRDA': 'recordingdate',
            'TRSN': 'internetradioname',
            'TRSO': 'internetradioowner',
            'TSIZ': 'size',
            'TSRC': 'isrc',
            'TSSE': 'encodingsettings',
            'TSST': 'setsubtitle',
        }
        
        for tag_id, tag_name in tag_mappings.items():
            if tag_id in audio_file.tags:
                tag_value = audio_file.tags[tag_id]
                # Textframes haben meist eine text-Eigenschaft
                if hasattr(tag_value, 'text') and tag_value.text:
                    tags[tag_name] = str(tag_value.text[0]) if tag_value.text else None
                else:
                    tags[tag_name] = str(tag_value)
        
        # TXXX (Benutzerdefinierte Text-Tags)
        for tag in audio_file.tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'TXXX':
                custom_key = f"custom_{tag.desc.lower().replace(' ', '_')}"
                if hasattr(tag, 'text') and tag.text:
                    tags[custom_key] = str(tag.text[0])
        
        # WXXX (Benutzerdefinierte URL-Tags)
        for tag in audio_file.tags.values():
            if hasattr(tag, 'desc') and tag.FrameID == 'WXXX':
                custom_key = f"url_{tag.desc.lower().replace(' ', '_')}"
                if hasattr(tag, 'url'):
                    tags[custom_key] = str(tag.url)
        
        # Spezielle Tags
        if 'APIC:' in str(audio_file.tags):
            tags['has_artwork'] = True
        
        return tags
    
    def _parse_filename(self, filename: str) -> Tuple[Optional[str], Optional[str], float]:
        """
        Versucht Künstler und Titel aus dem Dateinamen zu extrahieren.
        
        Args:
            filename: Dateiname (ohne Pfad)
            
        Returns:
            Tuple aus (Künstler, Titel, Confidence-Score)
        """
        # Dateierweiterung entfernen für besseres Matching
        name_without_ext = filename
        if '.' in filename:
            name_without_ext = '.'.join(filename.split('.')[:-1])
        
        # Verschiedene Patterns probieren
        for i, pattern in enumerate(self.filename_patterns):
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) >= 2:
                    # Confidence basierend auf Pattern-Reihenfolge
                    # Frühere Patterns sind zuverlässiger
                    confidence = 1.0 - (i * 0.1)
                    
                    artist = self._clean_string(groups[0])
                    title = self._clean_string(groups[1])
                    
                    # Spezielle Behandlung für Pattern 3 (Titel (Künstler))
                    if i == 2:  # Pattern: Titel (Künstler)
                        artist, title = title, artist
                    
                    logger.debug(f"Filename parsing: {filename} -> {artist} - {title} (confidence: {confidence:.2f})")
                    return artist, title, confidence
        
        # Fallback: Versuche einfache Trennung mit verschiedenen Separatoren
        separators = [' - ', ' _ ', ' feat. ', ' ft. ', ' featuring ']
        
        for separator in separators:
            if separator in name_without_ext:
                parts = name_without_ext.split(separator, 1)
                if len(parts) == 2:
                    artist = self._clean_string(parts[0])
                    title = self._clean_string(parts[1])
                    confidence = 0.3  # Niedrige Confidence für Fallback
                    
                    logger.debug(f"Fallback parsing: {filename} -> {artist} - {title} (confidence: {confidence:.2f})")
                    return artist, title, confidence
        
        # Kein Pattern gefunden
        logger.debug(f"Filename parsing failed: {filename}")
        return None, None, 0.0
    
    def _clean_string(self, text: str) -> str:
        """
        Bereinigt einen String von unerwünschten Zeichen.
        
        Args:
            text: Zu bereinigender Text
            
        Returns:
            Bereinigter Text
        """
        if not text:
            return ""
        
        # Führende/Abschließende Whitespaces entfernen
        cleaned = text.strip()
        
        # Mehrfache Leerzeichen zu einfachen Leerzeichen
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Unerwünschte Zeichen entfernen (aber Umlaute beibehalten)
        cleaned = re.sub(r'[^\w\s\-\.\(\)&äöüÄÖÜß]', '', cleaned)
        
        # Track-Nummern am Anfang entfernen
        cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
        cleaned = re.sub(r'^\d+\s*-\s*', '', cleaned)
        
        return cleaned.strip()
    
    def get_file_stats(self, mp3_files: List[Mp3FileInfo]) -> Dict[str, Any]:
        """
        Erstellt Statistiken über die gescannten Dateien.
        
        Args:
            mp3_files: Liste von Mp3FileInfo-Objekten
            
        Returns:
            Dictionary mit Statistiken
        """
        if not mp3_files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'total_duration_minutes': 0,
                'parsed_files': 0,
                'files_with_tags': 0,
                'avg_bitrate': 0,
                'avg_confidence': 0
            }
        
        total_size = sum(f.file_size for f in mp3_files)
        total_duration = sum(f.duration for f in mp3_files)
        parsed_files = sum(1 for f in mp3_files if f.parsed_artist and f.parsed_title)
        files_with_tags = sum(1 for f in mp3_files if f.existing_tags)
        avg_bitrate = sum(f.bitrate for f in mp3_files) / len(mp3_files)
        avg_confidence = sum(f.confidence for f in mp3_files) / len(mp3_files)
        
        return {
            'total_files': len(mp3_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_duration_minutes': round(total_duration / 60, 2),
            'parsed_files': parsed_files,
            'files_with_tags': files_with_tags,
            'avg_bitrate': round(avg_bitrate),
            'avg_confidence': round(avg_confidence, 2)
        }
