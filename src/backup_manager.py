"""
Advanced Backup Manager für MP3Tagger.

Bietet verschiedene Backup-Strategien:
1. Change-Log: Leichtgewichtige JSON-basierte Änderungsprotokolle
2. In-Memory: Temporäre RAM-basierte Backups für Transaktionen
3. Selective: Nur kritische Tags werden in kompakte Backups geschrieben

Für große Bibliotheken viel effizienter als komplette Datei-Kopien.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import tempfile
import os
import hashlib

from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError

logger = logging.getLogger(__name__)


class BackupStrategy(Enum):
    """Verfügbare Backup-Strategien."""
    CHANGELOG = "changelog"      # JSON-basierte Änderungsprotokolle
    IN_MEMORY = "in_memory"      # RAM-basierte Transaktionen
    SELECTIVE = "selective"      # Nur wichtige Tags als kompakte Backups
    FULL_COPY = "full_copy"      # Vollständige Dateikopien (Legacy)
    DISABLED = "disabled"        # Keine Backups


class BackupTransaction:
    """Transaktions-Container für In-Memory Backups."""
    
    def __init__(self, file_path: Path, original_data: bytes):
        self.file_path = file_path
        self.original_data = original_data
        self.timestamp = datetime.now()
        self.committed = False


class ChangeLogEntry:
    """Einzelner Eintrag im Change-Log."""
    
    def __init__(self, file_path: Path, old_tags: Dict[str, Any], 
                 new_tags: Dict[str, Any], operation: str = "update"):
        self.file_path = str(file_path)
        self.old_tags = old_tags
        self.new_tags = new_tags
        self.operation = operation
        self.timestamp = datetime.now().isoformat()
        self.file_hash = self._calculate_file_hash(file_path)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Berechnet SHA256-Hash der Datei für Integrität."""
        try:
            if not file_path.exists():
                return ""
            
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Lese nur die ersten 64KB für Performance
                hasher.update(f.read(65536))
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für JSON-Serialisierung."""
        return {
            'file_path': self.file_path,
            'old_tags': self._serialize_tags(self.old_tags),
            'new_tags': self._serialize_tags(self.new_tags),
            'operation': self.operation,
            'timestamp': self.timestamp,
            'file_hash': self.file_hash
        }
    
    def _serialize_tags(self, tags: Dict[str, Any]) -> Dict[str, Any]:
        """Serialisiert Tags für JSON."""
        serialized = {}
        for key, value in tags.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif hasattr(value, '__str__'):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChangeLogEntry':
        """Erstellt ChangeLogEntry aus Dictionary."""
        entry = cls.__new__(cls)
        entry.file_path = data['file_path']
        entry.old_tags = data['old_tags']
        entry.new_tags = data['new_tags']
        entry.operation = data['operation']
        entry.timestamp = data['timestamp']
        entry.file_hash = data.get('file_hash', '')
        return entry


class BackupManager:
    """
    Moderner Backup-Manager mit verschiedenen Strategien.
    
    Effizient für große MP3-Bibliotheken durch intelligente
    Backup-Strategien statt vollständiger Dateikopien.
    """
    
    def __init__(self, config):
        self.config = config
        self.backup_dir = Path(config.get('backup.directory', 'backups'))
        self.strategy = BackupStrategy(config.get('backup.strategy', 'changelog'))
        self.max_age_days = config.get('backup.max_age_days', 30)
        self.max_memory_mb = config.get('backup.max_memory_mb', 500)
        
        # Aktive In-Memory Transaktionen
        self._active_transactions: Dict[str, BackupTransaction] = {}
        
        # Critical Tags für Selective Backup
        self.critical_tags = set(config.get('backup.critical_tags', [
            'TIT2', 'TPE1', 'TALB', 'TDRC', 'TCON',  # Standard ID3
            'artist', 'title', 'album', 'date', 'genre'  # Mutagen Keys
        ]))
        
        self._ensure_directories()
        self._init_changelog_db()
    
    def _ensure_directories(self):
        """Erstellt notwendige Verzeichnisse."""
        if self.strategy != BackupStrategy.DISABLED:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Unterverzeichnisse für verschiedene Backup-Typen
            (self.backup_dir / 'changelogs').mkdir(exist_ok=True)
            (self.backup_dir / 'selective').mkdir(exist_ok=True)
            (self.backup_dir / 'full').mkdir(exist_ok=True)
    
    def _init_changelog_db(self):
        """Initialisiert SQLite-Datenbank für Change-Logs."""
        if self.strategy in [BackupStrategy.CHANGELOG]:
            self.changelog_db = self.backup_dir / 'changelog.db'
            
            with sqlite3.connect(self.changelog_db) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS change_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        old_tags TEXT,
                        new_tags TEXT,
                        file_hash TEXT,
                        timestamp TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_path 
                    ON change_log(file_path)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON change_log(timestamp)
                """)
    
    def create_backup(self, file_path: Path, current_tags: Optional[Dict[str, Any]] = None) -> bool:
        """
        Erstellt ein Backup basierend auf der konfigurierten Strategie.
        
        Args:
            file_path: Pfad zur MP3-Datei
            current_tags: Aktuelle Tags (optional, für Performance)
            
        Returns:
            True bei Erfolg
        """
        if self.strategy == BackupStrategy.DISABLED:
            return True
            
        try:
            if self.strategy == BackupStrategy.IN_MEMORY:
                return self._create_memory_backup(file_path)
            elif self.strategy == BackupStrategy.SELECTIVE:
                return self._create_selective_backup(file_path, current_tags)
            elif self.strategy == BackupStrategy.CHANGELOG:
                return self._prepare_changelog_backup(file_path, current_tags)
            elif self.strategy == BackupStrategy.FULL_COPY:
                return self._create_full_backup(file_path)
            
            return False
            
        except Exception as e:
            logger.error(f"Backup-Erstellung fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _create_memory_backup(self, file_path: Path) -> bool:
        """Erstellt In-Memory Backup für Transaktion."""
        try:
            # Prüfe Speicherlimit
            current_memory = sum(
                len(t.original_data) for t in self._active_transactions.values()
            ) / (1024 * 1024)  # MB
            
            if current_memory > self.max_memory_mb:
                logger.warning(f"Memory-Backup-Limit erreicht ({current_memory:.1f}MB)")
                return False
            
            # Lade Datei in Memory
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            transaction_id = str(file_path)
            self._active_transactions[transaction_id] = BackupTransaction(
                file_path, original_data
            )
            
            logger.debug(f"Memory-Backup erstellt für {file_path} "
                        f"({len(original_data)/1024:.1f}KB)")
            return True
            
        except Exception as e:
            logger.error(f"Memory-Backup fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _create_selective_backup(self, file_path: Path, 
                                current_tags: Optional[Dict[str, Any]] = None) -> bool:
        """Erstellt selektives Backup nur für kritische Tags."""
        try:
            if current_tags is None:
                current_tags = self._read_current_tags(file_path)
            
            # Filtere nur kritische Tags
            critical_backup = {
                key: value for key, value in current_tags.items()
                if key in self.critical_tags
            }
            
            # Erstelle kompaktes JSON-Backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = (self.backup_dir / 'selective' / 
                          f"{file_path.stem}_{timestamp}.json")
            
            backup_data = {
                'file_path': str(file_path),
                'timestamp': timestamp,
                'file_hash': self._calculate_file_hash(file_path),
                'critical_tags': self._serialize_tags(critical_backup)
            }
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Selective Backup erstellt: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Selective Backup fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _prepare_changelog_backup(self, file_path: Path, 
                                 current_tags: Optional[Dict[str, Any]] = None) -> bool:
        """Bereitet Change-Log Backup vor (wird bei write_tags finalisiert)."""
        try:
            if current_tags is None:
                current_tags = self._read_current_tags(file_path)
            
            # Speichere aktuelle Tags für späteren Vergleich
            transaction_id = str(file_path)
            self._active_transactions[transaction_id] = BackupTransaction(
                file_path, json.dumps(current_tags, default=str).encode()
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Changelog-Backup-Vorbereitung fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _create_full_backup(self, file_path: Path) -> bool:
        """Erstellt vollständige Dateikopie (Legacy-Modus)."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / 'full' / backup_filename
            
            import shutil
            shutil.copy2(file_path, backup_path)
            
            logger.debug(f"Full Backup erstellt: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Full Backup fehlgeschlagen für {file_path}: {e}")
            return False
    
    def finalize_changelog(self, file_path: Path, new_tags: Dict[str, Any], 
                          operation: str = "update") -> bool:
        """
        Finalisiert Change-Log Backup nach Tag-Änderungen.
        
        Args:
            file_path: Pfad zur geänderten Datei
            new_tags: Neue Tags die geschrieben wurden
            operation: Art der Operation (update, create, delete)
            
        Returns:
            True bei Erfolg
        """
        if self.strategy != BackupStrategy.CHANGELOG:
            return True
            
        try:
            transaction_id = str(file_path)
            if transaction_id not in self._active_transactions:
                logger.warning(f"Keine aktive Transaktion für {file_path}")
                return False
            
            transaction = self._active_transactions[transaction_id]
            old_tags = json.loads(transaction.original_data.decode())
            
            # Erstelle Change-Log Entry
            entry = ChangeLogEntry(file_path, old_tags, new_tags, operation)
            
            # Speichere in SQLite DB
            with sqlite3.connect(self.changelog_db) as conn:
                conn.execute("""
                    INSERT INTO change_log 
                    (file_path, operation, old_tags, new_tags, file_hash, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    entry.file_path,
                    entry.operation,
                    json.dumps(entry.old_tags, default=str),
                    json.dumps(entry.new_tags, default=str),
                    entry.file_hash,
                    entry.timestamp
                ))
            
            # Cleanup Transaction
            del self._active_transactions[transaction_id]
            
            logger.debug(f"Changelog finalisiert für {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Changelog-Finalisierung fehlgeschlagen für {file_path}: {e}")
            return False
    
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
        try:
            if self.strategy == BackupStrategy.IN_MEMORY:
                return self._restore_from_memory(file_path)
            elif self.strategy == BackupStrategy.CHANGELOG:
                return self._restore_from_changelog(file_path, backup_timestamp)
            elif self.strategy == BackupStrategy.SELECTIVE:
                return self._restore_from_selective(file_path, backup_timestamp)
            elif self.strategy == BackupStrategy.FULL_COPY:
                return self._restore_from_full_backup(file_path, backup_timestamp)
            
            logger.warning(f"Restore nicht unterstützt für Strategie: {self.strategy}")
            return False
            
        except Exception as e:
            logger.error(f"Restore fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _restore_from_memory(self, file_path: Path) -> bool:
        """Stellt aus In-Memory Backup wieder her."""
        transaction_id = str(file_path)
        if transaction_id not in self._active_transactions:
            logger.error(f"Keine Memory-Backup für {file_path}")
            return False
        
        try:
            transaction = self._active_transactions[transaction_id]
            with open(file_path, 'wb') as f:
                f.write(transaction.original_data)
            
            logger.info(f"Datei aus Memory-Backup wiederhergestellt: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Memory-Restore fehlgeschlagen für {file_path}: {e}")
            return False
    
    def _restore_from_changelog(self, file_path: Path, 
                               backup_timestamp: Optional[str] = None) -> bool:
        """Stellt aus Change-Log wieder her."""
        try:
            with sqlite3.connect(self.changelog_db) as conn:
                if backup_timestamp:
                    cursor = conn.execute("""
                        SELECT old_tags FROM change_log 
                        WHERE file_path = ? AND timestamp = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (str(file_path), backup_timestamp))
                else:
                    cursor = conn.execute("""
                        SELECT old_tags FROM change_log 
                        WHERE file_path = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (str(file_path),))
                
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Kein Changelog-Backup für {file_path}")
                    return False
                
                old_tags = json.loads(row[0])
                
                # Schreibe alte Tags zurück
                return self._write_tags_direct(file_path, old_tags)
                
        except Exception as e:
            logger.error(f"Changelog-Restore fehlgeschlagen für {file_path}: {e}")
            return False
    
    def commit_transaction(self, file_path: Path) -> bool:
        """Committet eine erfolgreiche Transaktion."""
        transaction_id = str(file_path)
        if transaction_id in self._active_transactions:
            self._active_transactions[transaction_id].committed = True
            
            # Bei In-Memory: Cleanup nach erfolgreichem Commit
            if self.strategy == BackupStrategy.IN_MEMORY:
                del self._active_transactions[transaction_id]
                logger.debug(f"Memory-Backup committed und freigegeben: {file_path}")
            
            return True
        return False
    
    def rollback_transaction(self, file_path: Path) -> bool:
        """Rollt eine fehlgeschlagene Transaktion zurück."""
        transaction_id = str(file_path)
        if transaction_id in self._active_transactions:
            if self.strategy == BackupStrategy.IN_MEMORY:
                success = self._restore_from_memory(file_path)
                del self._active_transactions[transaction_id]
                logger.info(f"Memory-Backup Rollback: {file_path}")
                return success
            else:
                del self._active_transactions[transaction_id]
        return True
    
    def cleanup_old_backups(self) -> int:
        """
        Entfernt alte Backups basierend auf max_age_days.
        
        Returns:
            Anzahl entfernter Backup-Dateien
        """
        removed_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
        
        try:
            # Cleanup Changelog DB
            if self.strategy == BackupStrategy.CHANGELOG and self.changelog_db.exists():
                with sqlite3.connect(self.changelog_db) as conn:
                    cursor = conn.execute("""
                        DELETE FROM change_log 
                        WHERE created_at < ?
                    """, (cutoff_date.isoformat(),))
                    removed_count += cursor.rowcount
            
            # Cleanup Backup-Dateien
            for backup_type in ['selective', 'full']:
                backup_subdir = self.backup_dir / backup_type
                if backup_subdir.exists():
                    for backup_file in backup_subdir.iterdir():
                        if backup_file.is_file():
                            file_age = datetime.fromtimestamp(backup_file.stat().st_mtime)
                            if file_age < cutoff_date:
                                backup_file.unlink()
                                removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Cleanup: {removed_count} alte Backups entfernt")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Backup-Cleanup fehlgeschlagen: {e}")
            return 0
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken über Backups zurück."""
        stats = {
            'strategy': self.strategy.value,
            'backup_dir': str(self.backup_dir),
            'active_transactions': len(self._active_transactions),
            'memory_usage_mb': 0.0,
            'total_backups': 0
        }
        
        try:
            # Memory Usage
            if self._active_transactions:
                total_bytes = sum(
                    len(t.original_data) for t in self._active_transactions.values()
                    if hasattr(t, 'original_data')
                )
                stats['memory_usage_mb'] = total_bytes / (1024 * 1024)
            
            # Changelog Stats
            if self.strategy == BackupStrategy.CHANGELOG and self.changelog_db.exists():
                with sqlite3.connect(self.changelog_db) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM change_log")
                    stats['changelog_entries'] = cursor.fetchone()[0]
            
            # File-based Backup Stats
            for backup_type in ['selective', 'full']:
                backup_subdir = self.backup_dir / backup_type
                if backup_subdir.exists():
                    count = len(list(backup_subdir.glob('*')))
                    stats[f'{backup_type}_backups'] = count
                    stats['total_backups'] += count
            
        except Exception as e:
            logger.error(f"Fehler beim Sammeln der Backup-Statistiken: {e}")
        
        return stats
    
    def _read_current_tags(self, file_path: Path) -> Dict[str, Any]:
        """Liest aktuelle Tags aus MP3-Datei."""
        try:
            audio = MP3(file_path)
            if audio.tags is None:
                return {}
            
            tags = {}
            for key, value in audio.tags.items():
                if hasattr(value, 'text'):
                    tags[key] = str(value.text[0]) if value.text else ""
                else:
                    tags[key] = str(value)
            
            return tags
            
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Tags von {file_path}: {e}")
            return {}
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Berechnet SHA256-Hash einer Datei."""
        try:
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Nur ersten Teil für Performance
                hasher.update(f.read(65536))
            return hasher.hexdigest()[:16]  # Kurzer Hash
        except Exception:
            return ""
    
    def _serialize_tags(self, tags: Dict[str, Any]) -> Dict[str, Any]:
        """Serialisiert Tags für JSON-Speicherung."""
        serialized = {}
        for key, value in tags.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = str(value)
        return serialized
    
    def _write_tags_direct(self, file_path: Path, tags: Dict[str, Any]) -> bool:
        """Schreibt Tags direkt ohne Backup-System."""
        try:
            # Diese Methode wird für Restore verwendet
            # Implementierung würde Tag-Writing ohne Backup-Aufrufe beinhalten
            logger.warning(f"Direct tag writing nicht implementiert für {file_path}")
            return False
        except Exception as e:
            logger.error(f"Direct tag writing fehlgeschlagen für {file_path}: {e}")
            return False
