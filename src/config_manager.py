"""
Configuration Manager für MP3 Tagger

Verwaltet die Lade- und Validierung von YAML-Konfigurationsdateien.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Verwaltet die Konfiguration des MP3 Taggers."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialisiert den ConfigManager.
        
        Args:
            config_path: Pfad zur Benutzerkonfigurationsdatei        """
        self.project_root = Path(__file__).parent.parent
        self.default_config_path = self.project_root / "config" / "default_config.yaml"
        self.user_config_path = Path(config_path) if config_path else (
            self.project_root / "config" / "user_config.yaml"
        )
        
        self.config = self._load_config()
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Lädt die Konfiguration aus Standard- und Benutzerdateien.
        
        Returns:
            Zusammengeführte Konfiguration
        """
        # Standard-Konfiguration laden
        default_config = self._load_yaml_file(self.default_config_path)
        
        # Benutzer-Konfiguration laden (falls vorhanden)
        user_config = {}
        if self.user_config_path.exists():
            user_config = self._load_yaml_file(self.user_config_path)
        else:
            print(f"Benutzer-Konfiguration nicht gefunden: {self.user_config_path}")
            print("Verwende Standard-Konfiguration. Erstelle user_config.yaml für individuelle Einstellungen.")
        
        # Konfigurationen zusammenführen
        merged_config = self._merge_configs(default_config, user_config)
        
        # Konfiguration validieren
        self._validate_config(merged_config)
        
        return merged_config
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Lädt eine YAML-Datei.
        
        Args:
            file_path: Pfad zur YAML-Datei
            
        Returns:
            Geladene Konfiguration
            
        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert
            yaml.YAMLError: Bei YAML-Parsing-Fehlern
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        except FileNotFoundError:
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {file_path}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Fehler beim Parsen der YAML-Datei {file_path}: {e}")
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Führt Standard- und Benutzer-Konfiguration zusammen.
        
        Args:
            default: Standard-Konfiguration
            user: Benutzer-Konfiguration
            
        Returns:
            Zusammengeführte Konfiguration
        """
        def deep_merge(base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict[str, Any]:
            """Rekursives Zusammenführen von Dictionaries."""
            result = base_dict.copy()
            
            for key, value in update_dict.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            
            return result
        
        return deep_merge(default, user)
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validiert die Konfiguration auf Vollständigkeit und Korrektheit.
        
        Args:
            config: Zu validierende Konfiguration
            
        Raises:
            ValueError: Bei ungültiger Konfiguration
        """
        required_sections = [
            'api_keys', 'tag_settings', 'matching_settings', 
            'youtube_settings', 'genre_settings', 'logging'
        ]
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Erforderlicher Konfigurationsabschnitt fehlt: {section}")
        
        # Validiere spezifische Einstellungen
        matching = config['matching_settings']
        if not (0 <= matching.get('min_confidence', 0) <= 100):
            raise ValueError("min_confidence muss zwischen 0 und 100 liegen")
        
        if not (0.0 <= matching.get('fuzzy_threshold', 0.0) <= 1.0):
            raise ValueError("fuzzy_threshold muss zwischen 0.0 und 1.0 liegen")
        
        # Validiere Log-Level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        log_level = config['logging'].get('level', 'INFO')
        if log_level not in valid_log_levels:
            raise ValueError(f"Ungültiger Log-Level: {log_level}. Erlaubt: {valid_log_levels}")
    
    def _setup_logging(self) -> None:
        """Konfiguriert das Logging-System basierend auf der Konfiguration."""
        log_config = self.config['logging']
        
        # Log-Verzeichnis erstellen
        log_file_path = self.project_root / log_config['file']
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Logging konfigurieren
        log_level = getattr(logging, log_config['level'])
        
        # Formatter definieren
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Root Logger konfigurieren
        logger = logging.getLogger()
        logger.setLevel(log_level)
        
        # Bestehende Handler entfernen
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File Handler
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=log_config.get('max_file_size', 10) * 1024 * 1024,
            backupCount=log_config.get('backup_count', 5),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console Handler (optional)
        if log_config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Holt einen Wert aus der Konfiguration.
        
        Args:
            key: Schlüssel (kann mit Punkten getrennt sein, z.B. 'api_keys.youtube_api_key')
            default: Standard-Wert falls Schlüssel nicht existiert
            
        Returns:
            Konfigurationswert oder Standard-Wert
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_api_key(self, service: str) -> Optional[str]:
        """
        Holt einen API-Schlüssel für einen bestimmten Service.
        
        Args:
            service: Name des Services (z.B. 'youtube_api_key')
            
        Returns:
            API-Schlüssel oder None
        """
        api_key = self.get(f'api_keys.{service}')
        return api_key if api_key and api_key.strip() else None
    
    def is_tag_protected(self, tag: str) -> bool:
        """
        Prüft, ob ein Tag geschützt ist.
        
        Args:
            tag: Tag-Name
            
        Returns:
            True wenn der Tag geschützt ist
        """
        protected_tags = self.get('tag_settings.protected_tags', [])
        return tag.lower() in [t.lower() for t in protected_tags]
    
    def is_tag_processable(self, tag: str) -> bool:
        """
        Prüft, ob ein Tag verarbeitet werden kann.
        
        Args:
            tag: Tag-Name
            
        Returns:
            True wenn der Tag verarbeitet werden kann
        """
        processable_tags = self.get('tag_settings.processable_tags', [])
        return tag.lower() in [t.lower() for t in processable_tags]
    
    def is_auto_update_tag(self, tag: str) -> bool:
        """
        Prüft, ob ein Tag automatisch aktualisiert werden soll.
        
        Args:
            tag: Tag-Name
            
        Returns:
            True wenn der Tag automatisch aktualisiert werden soll
        """
        auto_update_tags = self.get('tag_settings.auto_update_tags', [])
        return tag.lower() in [t.lower() for t in auto_update_tags]
    
    def get_custom_tag_mapping(self, tag: str) -> Optional[str]:
        """
        Holt das Mapping für einen benutzerdefinierten Tag.
        
        Args:
            tag: Tag-Name
            
        Returns:
            ID3-Tag-Mapping oder None
        """
        custom_tags = self.get('tag_settings.custom_tags', {})
        return custom_tags.get(tag)
    
    def create_user_config_template(self) -> None:
        """Erstellt eine Vorlage für die Benutzer-Konfiguration."""
        if self.user_config_path.exists():
            print(f"Benutzer-Konfiguration existiert bereits: {self.user_config_path}")
            return
        
        template_content = """# MP3 Tagger - Benutzer Konfiguration
# Hier können Sie die Standard-Konfiguration überschreiben

# API-Schlüssel (erforderlich für volle Funktionalität)
api_keys:
  # Last.fm API Key (kostenlos unter https://www.last.fm/api/account/create)
  lastfm_api_key: "DEIN_LASTFM_API_KEY"
  
  # Spotify API (kostenlos unter https://developer.spotify.com/)
  spotify_client_id: "DEIN_SPOTIFY_CLIENT_ID"
  spotify_client_secret: "DEIN_SPOTIFY_CLIENT_SECRET"
  
  # YouTube Data API v3 (Google Cloud Console)
  youtube_api_key: "DEIN_YOUTUBE_API_KEY"

# Überschreibe andere Einstellungen nach Bedarf
# matching_settings:
#   min_confidence: 85
#   fuzzy_threshold: 0.85

# logging:
#   level: "DEBUG"
#   console_output: true
"""
        
        try:
            with open(self.user_config_path, 'w', encoding='utf-8') as file:
                file.write(template_content)
            print(f"Benutzer-Konfigurationsvorlage erstellt: {self.user_config_path}")
            print("Bitte fügen Sie Ihre API-Schlüssel hinzu.")
        except Exception as e:
            print(f"Fehler beim Erstellen der Benutzer-Konfiguration: {e}")
    
    def update(self, key: str, value: Any) -> bool:
        """
        Aktualisiert einen Konfigurationswert in der Benutzerkonfiguration.
        
        Args:
            key: Konfigurationsschlüssel (z.B. "backup.strategy")
            value: Neuer Wert
            
        Returns:
            True bei Erfolg
        """
        try:
            # Lade aktuelle Benutzer-Konfiguration
            user_config = {}
            if self.user_config_path.exists():
                user_config = self._load_yaml_file(self.user_config_path)
            
            # Setze neuen Wert mit verschachtelten Schlüsseln
            keys = key.split('.')
            current_dict = user_config
            
            for k in keys[:-1]:
                if k not in current_dict:
                    current_dict[k] = {}
                current_dict = current_dict[k]
            
            current_dict[keys[-1]] = value
            
            # Speichere aktualisierte Konfiguration
            import yaml
            with open(self.user_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(user_config, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            
            # Lade Konfiguration neu
            self.config = self._load_config()
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Konfiguration: {e}")
            return False


# Globale Konfigurationsinstanz
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Holt die globale Konfigurationsinstanz.
    
    Args:
        config_path: Pfad zur Benutzerkonfigurationsdatei
        
    Returns:
        ConfigManager-Instanz
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ConfigManager(config_path)
    
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Lädt die Konfiguration neu.
    
    Args:
        config_path: Pfad zur Benutzerkonfigurationsdartei
        
    Returns:
        Neue ConfigManager-Instanz
    """
    global _config_instance
    _config_instance = ConfigManager(config_path)
    return _config_instance


def update_config(key: str, value: Any) -> bool:
    """
    Aktualisiert einen Konfigurationswert.
    
    Args:
        key: Konfigurationsschlüssel (z.B. "backup.strategy")
        value: Neuer Wert
        
    Returns:
        True bei Erfolg
    """
    config = get_config()
    return config.update(key, value)
