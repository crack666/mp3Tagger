"""
Konflikt Resolver für MP3 Tagger

Verwaltet die interaktive und automatische Auflösung von Tag-Konflikten.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import click

from .config_manager import get_config

logger = logging.getLogger(__name__)


class ConflictAction(Enum):
    """Aktionen für Konfliktauflösung."""
    KEEP_EXISTING = "keep_existing"
    USE_NEW = "use_new"
    SKIP = "skip"
    MERGE = "merge"
    ASK_LATER = "ask_later"


@dataclass
class TagConflict:
    """Repräsentiert einen Tag-Konflikt."""
    tag_name: str
    existing_value: Any
    new_value: Any
    confidence: float
    source: str
    is_protected: bool = False
    is_auto_update: bool = False
    recommended_action: ConflictAction = ConflictAction.KEEP_EXISTING


@dataclass
class ConflictResolution:
    """Resultat einer Konfliktauflösung."""
    action: ConflictAction
    final_value: Any
    user_decision: bool = False
    batch_applied: bool = False


class ConflictResolver:
    """Löst Konflikte zwischen vorhandenen und neuen Metadaten auf."""
    
    def __init__(self):
        """Initialisiert den ConflictResolver."""
        self.config = get_config()
        self.user_preferences = {}  # Gespeicherte Benutzer-Entscheidungen
        self.batch_rules = {}  # Regeln für Batch-Verarbeitung
        
    def analyze_conflicts(
        self, 
        existing_tags: Dict[str, Any], 
        new_metadata: Dict[str, Any],
        confidence: float = 0.0,
        source: str = "unknown"
    ) -> List[TagConflict]:
        """
        Analysiert Konflikte zwischen vorhandenen und neuen Tags.
        
        Args:
            existing_tags: Vorhandene Tags
            new_metadata: Neue Metadaten
            confidence: Confidence-Score der neuen Daten
            source: Quelle der neuen Daten
            
        Returns:
            Liste von TagConflict-Objekten
        """
        conflicts = []
        
        for tag_name, new_value in new_metadata.items():
            if tag_name in existing_tags and existing_tags[tag_name]:
                existing_value = existing_tags[tag_name]
                
                # Werte vergleichen (normalisiert)
                if not self._values_equal(existing_value, new_value):
                    conflict = TagConflict(
                        tag_name=tag_name,
                        existing_value=existing_value,
                        new_value=new_value,
                        confidence=confidence,
                        source=source,
                        is_protected=self.config.is_tag_protected(tag_name),
                        is_auto_update=self.config.is_auto_update_tag(tag_name),
                        recommended_action=self._get_recommended_action(
                            tag_name, existing_value, new_value, confidence
                        )
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _values_equal(self, value1: Any, value2: Any) -> bool:
        """Prüft ob zwei Werte als gleich betrachtet werden können."""
        # Strings normalisieren
        if isinstance(value1, str) and isinstance(value2, str):
            return value1.strip().lower() == value2.strip().lower()
        
        # Listen vergleichen
        if isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                return False
            return all(self._values_equal(v1, v2) for v1, v2 in zip(value1, value2))
        
        # Numerische Werte
        try:
            return float(value1) == float(value2)
        except (ValueError, TypeError):
            pass
        
        # Standard-Vergleich
        return value1 == value2
    
    def _get_recommended_action(
        self, 
        tag_name: str, 
        existing_value: Any, 
        new_value: Any, 
        confidence: float
    ) -> ConflictAction:
        """Bestimmt die empfohlene Aktion für einen Konflikt."""
        
        # Geschützte Tags niemals überschreiben
        if self.config.is_tag_protected(tag_name):
            return ConflictAction.KEEP_EXISTING
        
        # Auto-Update Tags automatisch aktualisieren
        if self.config.is_auto_update_tag(tag_name):
            return ConflictAction.USE_NEW
        
        # Hohe Confidence-Scores bevorzugen
        min_confidence = self.config.get('matching_settings.min_confidence', 80) / 100
        if confidence >= min_confidence:
            # Spezielle Regeln für verschiedene Tag-Typen
            if tag_name in ['youtube_views', 'spotify_popularity', 'popularity_score']:
                # Aktuelle Zahlen sind meist besser
                return ConflictAction.USE_NEW
            elif tag_name in ['genre', 'genres']:
                # Genres können zusammengeführt werden
                return ConflictAction.MERGE
            elif tag_name in ['year', 'date']:
                # Spezifischere Daten bevorzugen
                if len(str(new_value)) > len(str(existing_value)):
                    return ConflictAction.USE_NEW
            elif not existing_value or str(existing_value).strip() == "":
                # Leere Werte ersetzen
                return ConflictAction.USE_NEW
        
        # Standard: Vorhandene Werte behalten
        return ConflictAction.KEEP_EXISTING
    
    def resolve_conflicts_interactive(
        self, 
        conflicts: List[TagConflict], 
        file_path: str
    ) -> Dict[str, ConflictResolution]:
        """
        Löst Konflikte interaktiv mit Benutzer-Input auf.
        
        Args:
            conflicts: Liste von Konflikten
            file_path: Pfad zur betroffenen Datei
            
        Returns:
            Dictionary mit Konflikt-Auflösungen
        """
        resolutions = {}
        
        if not conflicts:
            return resolutions
        
        click.echo(f"\n🔍 Konflikte gefunden in: {file_path}")
        click.echo("=" * 60)
        
        for i, conflict in enumerate(conflicts, 1):
            click.echo(f"\nKonflikt {i}/{len(conflicts)}: {conflict.tag_name}")
            click.echo("-" * 40)
            click.echo(f"Vorhandener Wert: {conflict.existing_value}")
            click.echo(f"Neuer Wert: {conflict.new_value}")
            click.echo(f"Quelle: {conflict.source}")
            click.echo(f"Confidence: {conflict.confidence:.2f}")
            
            if conflict.is_protected:
                click.echo("⚠️  Geschützter Tag - wird nicht geändert")
                resolutions[conflict.tag_name] = ConflictResolution(
                    action=ConflictAction.KEEP_EXISTING,
                    final_value=conflict.existing_value,
                    user_decision=False
                )
                continue
            
            if conflict.is_auto_update:
                click.echo("🔄 Auto-Update Tag - wird automatisch aktualisiert")
                resolutions[conflict.tag_name] = ConflictResolution(
                    action=ConflictAction.USE_NEW,
                    final_value=conflict.new_value,
                    user_decision=False
                )
                continue
            
            # Benutzer-Entscheidung
            resolution = self._get_user_decision(conflict)
            resolutions[conflict.tag_name] = resolution
        
        return resolutions
    
    def _get_user_decision(self, conflict: TagConflict) -> ConflictResolution:
        """Holt eine Benutzer-Entscheidung für einen Konflikt."""
        
        # Prüfe gespeicherte Präferenzen
        preference_key = f"{conflict.tag_name}:{conflict.source}"
        if preference_key in self.user_preferences:
            action = self.user_preferences[preference_key]
            final_value = self._apply_action(conflict, action)
            return ConflictResolution(
                action=action,
                final_value=final_value,
                user_decision=True,
                batch_applied=True
            )
        
        # Interaktive Entscheidung
        choices = [
            ("k", "Vorhandenen Wert behalten"),
            ("n", "Neuen Wert verwenden"),
            ("s", "Überspringen (nicht ändern)"),
        ]
        
        # Merge-Option für kompatible Tags
        if conflict.tag_name in ['genre', 'genres']:
            choices.append(("m", "Werte zusammenführen"))
        
        choices.extend([
            ("a", "Für alle ähnlichen Konflikte anwenden"),
            ("h", "Hilfe anzeigen")
        ])
        
        while True:
            click.echo(f"\nEmpfehlung: {conflict.recommended_action.value}")
            choice_str = " / ".join([f"({c}) {desc}" for c, desc in choices])
            click.echo(f"Optionen: {choice_str}")
            
            choice = click.prompt("Ihre Wahl", type=str, default="k").lower()
            
            if choice == "k":
                action = ConflictAction.KEEP_EXISTING
                break
            elif choice == "n":
                action = ConflictAction.USE_NEW
                break
            elif choice == "s":
                action = ConflictAction.SKIP
                break
            elif choice == "m" and conflict.tag_name in ['genre', 'genres']:
                action = ConflictAction.MERGE
                break
            elif choice == "a":
                # Batch-Regel erstellen
                action = self._get_batch_action()
                if action:
                    self.user_preferences[preference_key] = action
                    break
            elif choice == "h":
                self._show_help()
                continue
            else:
                click.echo("Ungültige Wahl. Bitte versuchen Sie es erneut.")
                continue
        
        final_value = self._apply_action(conflict, action)
        return ConflictResolution(
            action=action,
            final_value=final_value,
            user_decision=True
        )
    
    def _get_batch_action(self) -> Optional[ConflictAction]:
        """Holt eine Batch-Aktion vom Benutzer."""
        click.echo("\n🔄 Batch-Aktion auswählen:")
        click.echo("(k) Alle vorhandenen Werte behalten")
        click.echo("(n) Alle neuen Werte verwenden")
        click.echo("(s) Alle überspringen")
        
        choice = click.prompt("Batch-Aktion", type=str).lower()
        
        if choice == "k":
            return ConflictAction.KEEP_EXISTING
        elif choice == "n":
            return ConflictAction.USE_NEW
        elif choice == "s":
            return ConflictAction.SKIP
        else:
            click.echo("Ungültige Wahl.")
            return None
    
    def _apply_action(self, conflict: TagConflict, action: ConflictAction) -> Any:
        """Wendet eine Aktion auf einen Konflikt an."""
        if action == ConflictAction.KEEP_EXISTING:
            return conflict.existing_value
        elif action == ConflictAction.USE_NEW:
            return conflict.new_value
        elif action == ConflictAction.MERGE:
            return self._merge_values(conflict.existing_value, conflict.new_value)
        elif action == ConflictAction.SKIP:
            return conflict.existing_value
        else:
            return conflict.existing_value
    
    def _merge_values(self, existing: Any, new: Any) -> Any:
        """Führt zwei Werte zusammen (für kompatible Datentypen)."""
        # Genre-Listen zusammenführen
        if isinstance(existing, list) and isinstance(new, list):
            merged = existing.copy()
            for item in new:
                if item not in merged:
                    merged.append(item)
            return merged
        
        # Strings als Listen behandeln (getrennt durch Komma/Semikolon)
        if isinstance(existing, str) and isinstance(new, str):
            # Trennen und zusammenführen
            separators = [';', ',', '|']
            for sep in separators:
                if sep in existing or sep in new:
                    existing_list = [item.strip() for item in existing.split(sep) if item.strip()]
                    new_list = [item.strip() for item in new.split(sep) if item.strip()]
                    
                    merged = existing_list.copy()
                    for item in new_list:
                        if item not in merged:
                            merged.append(item)
                    
                    return sep.join(merged)
            
            # Keine Separatoren gefunden - als separate Items behandeln
            if existing != new:
                return f"{existing}; {new}"
        
        # Standard: Neuen Wert verwenden
        return new
    
    def _show_help(self):
        """Zeigt Hilfe-Informationen an."""
        click.echo("\n📚 HILFE - Konfliktauflösung")
        click.echo("=" * 40)
        click.echo("(k) Behalten: Vorhandener Wert wird nicht geändert")
        click.echo("(n) Neu: Neuer Wert ersetzt den vorhandenen")
        click.echo("(s) Überspringen: Tag wird nicht aktualisiert")
        click.echo("(m) Merge: Werte werden zusammengeführt (nur für kompatible Tags)")
        click.echo("(a) Batch: Aktion auf alle ähnlichen Konflikte anwenden")
        click.echo("\n💡 Tipps:")
        click.echo("- Hohe Confidence-Scores (>0.8) sind meist zuverlässig")
        click.echo("- Geschützte Tags (z.B. Kommentare) werden nie überschrieben")
        click.echo("- Auto-Update Tags werden automatisch aktualisiert")
        click.echo("- Batch-Aktionen sparen Zeit bei vielen ähnlichen Konflikten")
    
    def resolve_conflicts_automatic(
        self, 
        conflicts: List[TagConflict]
    ) -> Dict[str, ConflictResolution]:
        """
        Löst Konflikte automatisch basierend auf Regeln auf.
        
        Args:
            conflicts: Liste von Konflikten
            
        Returns:
            Dictionary mit Konflikt-Auflösungen
        """
        resolutions = {}
        
        for conflict in conflicts:
            action = conflict.recommended_action
            final_value = self._apply_action(conflict, action)
            
            resolutions[conflict.tag_name] = ConflictResolution(
                action=action,
                final_value=final_value,
                user_decision=False
            )
            
            logger.debug(
                f"Automatische Auflösung: {conflict.tag_name} -> {action.value}"
            )
        
        return resolutions
    
    def get_conflict_summary(self, conflicts: List[TagConflict]) -> Dict[str, int]:
        """
        Erstellt eine Zusammenfassung der Konflikte.
        
        Args:
            conflicts: Liste von Konflikten
            
        Returns:
            Dictionary mit Konflikt-Statistiken
        """
        summary = {
            'total': len(conflicts),
            'protected': 0,
            'auto_update': 0,
            'high_confidence': 0,
            'by_tag': {},
            'by_source': {}
        }
        
        for conflict in conflicts:
            if conflict.is_protected:
                summary['protected'] += 1
            if conflict.is_auto_update:
                summary['auto_update'] += 1
            if conflict.confidence >= 0.8:
                summary['high_confidence'] += 1
            
            # Nach Tag-Name
            if conflict.tag_name not in summary['by_tag']:
                summary['by_tag'][conflict.tag_name] = 0
            summary['by_tag'][conflict.tag_name] += 1
            
            # Nach Quelle
            if conflict.source not in summary['by_source']:
                summary['by_source'][conflict.source] = 0
            summary['by_source'][conflict.source] += 1
        
        return summary
    
    def save_user_preferences(self, file_path: str = "user_preferences.json"):
        """Speichert Benutzer-Präferenzen für spätere Nutzung."""
        try:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                # Konvertiere Enum-Werte zu Strings
                preferences = {
                    key: action.value if isinstance(action, ConflictAction) else action
                    for key, action in self.user_preferences.items()
                }
                json.dump(preferences, f, ensure_ascii=False, indent=2)
            logger.info(f"Benutzer-Präferenzen gespeichert: {file_path}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Präferenzen: {e}")
    
    def load_user_preferences(self, file_path: str = "user_preferences.json"):
        """Lädt gespeicherte Benutzer-Präferenzen."""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                preferences = json.load(f)
                # Konvertiere Strings zurück zu Enum-Werten
                self.user_preferences = {
                    key: ConflictAction(value)
                    for key, value in preferences.items()
                }
            logger.info(f"Benutzer-Präferenzen geladen: {file_path}")
        except FileNotFoundError:
            logger.debug("Keine gespeicherten Präferenzen gefunden")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Präferenzen: {e}")
    
    def clear_user_preferences(self):
        """Löscht alle gespeicherten Benutzer-Präferenzen."""
        self.user_preferences.clear()
        self.batch_rules.clear()
        logger.info("Benutzer-Präferenzen gelöscht")
