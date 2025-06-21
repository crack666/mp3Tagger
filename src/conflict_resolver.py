"""
Konflikt Resolver für MP3 Tagger

Verwaltet die interaktive und automatische Auflösung von Tag-Konflikten.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import click
from collections import defaultdict, Counter
from datetime import datetime

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


@dataclass
class BatchRule:
    """Regel für Batch-Verarbeitung von Konflikten."""
    pattern: str  # Tag-Pattern (z.B. "youtube_*", "spotify_*")
    action: ConflictAction
    applies_to: str  # "tag", "source", "confidence_range"
    condition: str  # Zusätzliche Bedingung
    created_at: str
    usage_count: int = 0


@dataclass
class ConflictSession:
    """Verwaltet eine Konflikt-Session für Batch-Verarbeitung."""
    total_conflicts: int = 0
    resolved_automatically: int = 0
    resolved_interactively: int = 0
    batch_rules_applied: int = 0
    user_interruptions: int = 0
    start_time: str = ""
    
    def get_efficiency_score(self) -> float:
        """Berechnet Effizienz-Score der Session (0-1)."""
        if self.total_conflicts == 0:
            return 1.0
        return (self.resolved_automatically + self.batch_rules_applied) / self.total_conflicts


class ConflictResolver:
    """Löst Konflikte zwischen vorhandenen und neuen Metadaten auf."""
    
    def __init__(self, config=None):
        """Initialisiert den ConflictResolver."""
        self.config = config or get_config()
        self.user_preferences = {}  # Gespeicherte Benutzer-Entscheidungen
        self.batch_rules = {}  # Regeln für Batch-Verarbeitung
        self.session = ConflictSession()  # Aktuelle Session
        self.conflict_stats = defaultdict(int)  # Statistiken
        
        # Lade gespeicherte Batch-Rules
        self._load_batch_rules()
    
    def _load_batch_rules(self):
        """Lädt gespeicherte Batch-Rules."""
        try:
            import json
            from pathlib import Path
            
            rules_file = Path("batch_rules.json")
            if rules_file.exists():
                with open(rules_file, 'r', encoding='utf-8') as f:
                    rules_data = json.load(f)
                    self.batch_rules = {
                        key: BatchRule(**rule_data)
                        for key, rule_data in rules_data.items()
                    }
                logger.info(f"Batch-Rules geladen: {len(self.batch_rules)}")
        except Exception as e:
            logger.debug(f"Fehler beim Laden der Batch-Rules: {e}")
    
    def _save_batch_rules(self):
        """Speichert Batch-Rules."""
        try:
            import json
            from pathlib import Path
            
            rules_data = {
                key: {
                    'pattern': rule.pattern,
                    'action': rule.action.value,
                    'applies_to': rule.applies_to,
                    'condition': rule.condition,
                    'created_at': rule.created_at,
                    'usage_count': rule.usage_count
                }
                for key, rule in self.batch_rules.items()
            }
            
            with open("batch_rules.json", 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, indent=2, ensure_ascii=False)
            logger.info("Batch-Rules gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Batch-Rules: {e}")
    
    def _is_auto_update_tag(self, tag_name: str) -> bool:
        """Prüft ob ein Tag automatisch aktualisiert werden soll."""
        auto_update_tags = self.config.get('conflict_management.auto_update_tags', [])
        
        # Exakte Übereinstimmung
        if tag_name in auto_update_tags:
            return True
            
        # Pattern-Matching (z.B. youtube_*, spotify_*)

        for pattern in auto_update_tags:
            if '*' in pattern:
                prefix = pattern.replace('*', '')
                if tag_name.startswith(prefix):
                    return True
        
        return False
    
    def _is_protected_tag(self, tag_name: str) -> bool:
        """Prüft ob ein Tag geschützt ist."""
        protected_tags = self.config.get('conflict_management.protected_tags', [])
        return tag_name in protected_tags
    
    def _requires_interaction(self, tag_name: str) -> bool:
        """Prüft ob ein Tag interaktive Behandlung erfordert."""
        interactive_tags = self.config.get('conflict_management.interactive_tags', [])
        return tag_name in interactive_tags

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
    
    def resolve_metadata_conflicts(
        self, 
        current_tags: Dict[str, Any], 
        enrichment_data: Dict[str, Any],
        file_path: str = "",
        interactive: bool = False
    ) -> Dict[str, Any]:
        """
        Intelligente Hauptmethode zur Auflösung von Metadaten-Konflikten.
        
        Args:
            current_tags: Vorhandene Tags der Datei
            enrichment_data: Neue Metadaten aus APIs
            file_path: Pfad zur Datei (für Logging)
            interactive: Ob interaktive Auflösung verwendet werden soll
            
        Returns:
            Dictionary mit aufgelösten Tags
        """
        # Session-Start
        if self.session.total_conflicts == 0:
            self.session.start_time = datetime.now().isoformat()
        
        # Konflikte identifizieren
        conflicts = self._identify_conflicts(current_tags, enrichment_data)
        self.session.total_conflicts += len(conflicts)
        
        if not conflicts:
            # Keine Konflikte - einfach neue Daten hinzufügen
            resolved_tags = current_tags.copy()
            for source, metadata in enrichment_data.items():
                for tag_name, value in metadata.items():
                    if tag_name not in resolved_tags:
                        resolved_tags[tag_name] = value
            return resolved_tags
        
        logger.debug(f"Gefundene Konflikte: {len(conflicts)} für {file_path or 'Datei'}")
        
        # Intelligente Kategorisierung der Konflikte
        auto_conflicts, interactive_conflicts, protected_conflicts = self._categorize_conflicts(conflicts)
        
        # 1. Automatische Auflösung (Auto-Update Tags)
        auto_resolutions = {}
        for conflict in auto_conflicts:
            auto_resolutions[conflict.tag_name] = ConflictResolution(
                action=ConflictAction.USE_NEW,
                final_value=conflict.new_value,
                user_decision=False
            )
            self.session.resolved_automatically += 1
        
        # 2. Geschützte Tags (immer behalten)
        protected_resolutions = {}
        for conflict in protected_conflicts:
            protected_resolutions[conflict.tag_name] = ConflictResolution(
                action=ConflictAction.KEEP_EXISTING,
                final_value=conflict.existing_value,
                user_decision=False
            )
            self.session.resolved_automatically += 1
        
        # 3. Batch-Rules anwenden
        batch_resolutions = {}
        remaining_conflicts = []
        for conflict in interactive_conflicts:
            batch_resolution = self._apply_batch_rules(conflict)
            if batch_resolution:
                batch_resolutions[conflict.tag_name] = batch_resolution
                self.session.batch_rules_applied += 1
            else:
                remaining_conflicts.append(conflict)
        
        # 4. Interaktive Auflösung nur für verbleibende Konflikte
        interactive_resolutions = {}
        if interactive and remaining_conflicts:
            # Prüfe ob Batch-Mode angeboten werden soll
            if (len(remaining_conflicts) >= self.config.get('conflict_management.batch_processing.auto_batch_threshold', 5) 
                and self.config.get('conflict_management.batch_processing.enabled', True)):
                
                interactive_resolutions = self._resolve_with_batch_options(remaining_conflicts, file_path)
            else:
                interactive_resolutions = self.resolve_conflicts_interactive(remaining_conflicts, file_path)
            
            self.session.resolved_interactively += len(interactive_resolutions)
        else:
            # Fallback: Automatische Auflösung basierend auf Confidence
            for conflict in remaining_conflicts:
                resolution = self._resolve_by_confidence(conflict)
                interactive_resolutions[conflict.tag_name] = resolution
                self.session.resolved_automatically += 1
        
        # Alle Auflösungen zusammenführen
        all_resolutions = {**auto_resolutions, **protected_resolutions, 
                          **batch_resolutions, **interactive_resolutions}
        
        # Finale Tags zusammenstellen
        resolved_tags = current_tags.copy()
        
        for conflict in conflicts:
            resolution = all_resolutions.get(conflict.tag_name)
            if resolution and resolution.action != ConflictAction.SKIP:
                resolved_tags[conflict.tag_name] = resolution.final_value
        
        # Neue Tags hinzufügen (ohne Konflikte)
        for source, metadata in enrichment_data.items():
            for tag_name, value in metadata.items():
                if tag_name not in resolved_tags:
                    resolved_tags[tag_name] = value
        
        return resolved_tags
    
    def _categorize_conflicts(self, conflicts: List[TagConflict]) -> Tuple[List[TagConflict], List[TagConflict], List[TagConflict]]:
        """Kategorisiert Konflikte in Auto-Update, Interactive und Protected."""
        auto_conflicts = []
        interactive_conflicts = []
        protected_conflicts = []
        
        for conflict in conflicts:
            if self._is_protected_tag(conflict.tag_name):
                protected_conflicts.append(conflict)
            elif self._is_auto_update_tag(conflict.tag_name):
                auto_conflicts.append(conflict)
            else:
                interactive_conflicts.append(conflict)
        
        return auto_conflicts, interactive_conflicts, protected_conflicts
    
    def _apply_batch_rules(self, conflict: TagConflict) -> Optional[ConflictResolution]:
        """Wendet Batch-Rules auf einen Konflikt an."""
        for rule_key, rule in self.batch_rules.items():
            if self._rule_matches(rule, conflict):
                rule.usage_count += 1
                return ConflictResolution(
                    action=rule.action,
                    final_value=self._apply_action(conflict, rule.action),
                    user_decision=False,
                    batch_applied=True
                )
        return None
    
    def _rule_matches(self, rule: BatchRule, conflict: TagConflict) -> bool:
        """Prüft ob eine Batch-Rule auf einen Konflikt anwendbar ist."""
        if rule.applies_to == "tag":
            if '*' in rule.pattern:
                prefix = rule.pattern.replace('*', '')
                return conflict.tag_name.startswith(prefix)
            else:
                return conflict.tag_name == rule.pattern
        elif rule.applies_to == "source":
            return conflict.source == rule.pattern
        elif rule.applies_to == "confidence_range":
            min_conf, max_conf = map(float, rule.pattern.split('-'))
            return min_conf <= conflict.confidence <= max_conf
        
        return False
    
    def _resolve_by_confidence(self, conflict: TagConflict) -> ConflictResolution:
        """Löst Konflikt basierend auf Confidence-Score."""
        thresholds = self.config.get('conflict_management.confidence_thresholds', {})
        
        if conflict.confidence >= thresholds.get('auto_accept', 0.95):
            action = ConflictAction.USE_NEW
        elif conflict.confidence < thresholds.get('warn_low_confidence', 0.60):
            action = ConflictAction.KEEP_EXISTING
        else:
            action = conflict.recommended_action
        
        return ConflictResolution(
            action=action,
            final_value=self._apply_action(conflict, action),
            user_decision=False
        )
    
    def _resolve_with_batch_options(self, conflicts: List[TagConflict], file_path: str) -> Dict[str, ConflictResolution]:
        """Löst Konflikte mit Batch-Optionen."""
        if not conflicts:
            return {}
        
        click.echo(f"\n🔄 Batch-Verarbeitung für {len(conflicts)} Konflikte in: {file_path}")
        click.echo("=" * 70)
        
        # Gruppiere Konflikte nach Ähnlichkeit
        conflict_groups = self._group_similar_conflicts(conflicts)
        
        resolutions = {}
        
        for group_name, group_conflicts in conflict_groups.items():
            click.echo(f"\n📦 Konflikt-Gruppe: {group_name} ({len(group_conflicts)} Konflikte)")
            
            # Zeige Beispiel-Konflikt
            example = group_conflicts[0]
            click.echo(f"Beispiel - {example.tag_name}:")
            click.echo(f"  Vorhandener Wert: {example.existing_value}")
            click.echo(f"  Neuer Wert: {example.new_value}")
            click.echo(f"  Quelle: {example.source}")
            click.echo(f"  Confidence: {example.confidence:.2f}")
            
            # Batch-Optionen
            choices = [
                ("k", f"Alle {len(group_conflicts)} vorhandenen Werte behalten"),
                ("n", f"Alle {len(group_conflicts)} neuen Werte verwenden"),
                ("s", f"Alle {len(group_conflicts)} überspringen"),
                ("i", "Einzeln entscheiden"),
                ("r", "Batch-Rule erstellen und anwenden")
            ]
            
            choice = click.prompt(
                "\nWie möchten Sie diese Gruppe behandeln? " + 
                " / ".join([f"({c}) {desc}" for c, desc in choices]),
                type=click.Choice([c for c, _ in choices], case_sensitive=False)
            ).lower()
            
            if choice == 'r':
                # Neue Batch-Rule erstellen
                rule = self._create_batch_rule(group_conflicts, group_name)
                if rule:
                    self.batch_rules[f"{group_name}_{len(self.batch_rules)}"] = rule
                    self._save_batch_rules()
                    
                    # Rule auf alle Konflikte der Gruppe anwenden
                    for conflict in group_conflicts:
                        resolution = ConflictResolution(
                            action=rule.action,
                            final_value=self._apply_action(conflict, rule.action),
                            user_decision=True,
                            batch_applied=True
                        )
                        resolutions[conflict.tag_name] = resolution
                continue
            
            # Standard-Actions
            if choice == 'i':
                # Einzelne Behandlung
                for conflict in group_conflicts:
                    resolution = self._get_user_decision(conflict)
                    resolutions[conflict.tag_name] = resolution
            else:
                # Batch-Action
                action_map = {'k': ConflictAction.KEEP_EXISTING, 'n': ConflictAction.USE_NEW, 's': ConflictAction.SKIP}
                action = action_map[choice]
                
                for conflict in group_conflicts:
                    resolution = ConflictResolution(
                        action=action,
                        final_value=self._apply_action(conflict, action),
                        user_decision=True,
                        batch_applied=True
                    )
                    resolutions[conflict.tag_name] = resolution
        
        return resolutions
    
    def _group_similar_conflicts(self, conflicts: List[TagConflict]) -> Dict[str, List[TagConflict]]:
        """Gruppiert Konflikte nach Ähnlichkeit."""
        groups = defaultdict(list)
        
        for conflict in conflicts:
            # Gruppierung nach Tag-Präfix
            if '_' in conflict.tag_name:
                prefix = conflict.tag_name.split('_')[0]
                group_key = f"{prefix}_*"
            else:
                group_key = conflict.tag_name
            
            groups[group_key].append(conflict)
        
        return dict(groups)
    
    def _create_batch_rule(self, conflicts: List[TagConflict], group_name: str) -> Optional[BatchRule]:
        """Erstellt eine neue Batch-Rule interaktiv."""
        click.echo(f"\n🛠️  Batch-Rule für '{group_name}' erstellen:")
        
        # Action wählen
        actions = [
            (ConflictAction.KEEP_EXISTING, "Vorhandene Werte immer behalten"),
            (ConflictAction.USE_NEW, "Neue Werte immer verwenden"),
            (ConflictAction.SKIP, "Immer überspringen")
        ]
        
        click.echo("Verfügbare Aktionen:")
        for i, (action, desc) in enumerate(actions, 1):
            click.echo(f"  {i}. {desc}")
        
        choice = click.prompt("Wählen Sie eine Aktion", type=click.IntRange(1, len(actions)))
        selected_action = actions[choice - 1][0]
        
        # Bedingung wählen
        conditions = [
            ("tag", f"Für alle Tags mit Pattern '{group_name}'"),
            ("source", "Für alle Konflikte von einer bestimmten Quelle"),
            ("confidence_range", "Für einen bestimmten Confidence-Bereich")
        ]
        
        click.echo("\nAnwendungsbereich:")
        for i, (cond_type, desc) in enumerate(conditions, 1):
            click.echo(f"  {i}. {desc}")
        
        cond_choice = click.prompt("Wählen Sie den Anwendungsbereich", type=click.IntRange(1, len(conditions)))
        applies_to, _ = conditions[cond_choice - 1]
        
        pattern = group_name
        if applies_to == "source":
            sources = list(set(c.source for c in conflicts))
            click.echo(f"Verfügbare Quellen: {', '.join(sources)}")
            pattern = click.prompt("Quelle wählen", type=click.Choice(sources))
        elif applies_to == "confidence_range":
            pattern = click.prompt("Confidence-Bereich (z.B. 0.8-1.0)", type=str)
        
        rule = BatchRule(
            pattern=pattern,
            action=selected_action,
            applies_to=applies_to,
            condition="",
            created_at=datetime.now().isoformat()
        )
        
        click.echo(f"✅ Batch-Rule erstellt: {rule.pattern} → {rule.action.value}")
        return rule
    
    def get_session_summary(self) -> str:
        """Erstellt eine Zusammenfassung der aktuellen Session."""
        if self.session.total_conflicts == 0:
            return "Keine Konflikte in dieser Session."
        
        efficiency = self.session.get_efficiency_score()
        
        summary = f"""
🔄 Konflikt-Session Zusammenfassung:
{'='*50}
Gesamt-Konflikte: {self.session.total_conflicts}
Automatisch gelöst: {self.session.resolved_automatically} ({self.session.resolved_automatically/self.session.total_conflicts*100:.1f}%)
Interaktiv gelöst: {self.session.resolved_interactively} ({self.session.resolved_interactively/self.session.total_conflicts*100:.1f}%)
Batch-Rules angewendet: {self.session.batch_rules_applied} ({self.session.batch_rules_applied/self.session.total_conflicts*100:.1f}%)
Effizienz-Score: {efficiency:.2f}/1.0 {'🟢' if efficiency > 0.8 else '🟡' if efficiency > 0.5 else '🔴'}

💡 Gespeicherte Batch-Rules: {len(self.batch_rules)}
"""
        return summary
    
    def reset_session(self):
        """Setzt die aktuelle Session zurück."""
        self.session = ConflictSession()
        self.conflict_stats.clear()

    def _identify_conflicts(
        self, 
        current_tags: Dict[str, Any], 
        enrichment_data: Dict[str, Any]
    ) -> List[TagConflict]:
        """Identifiziert Konflikte zwischen vorhandenen und neuen Tags."""
        conflicts = []
        
        for source, metadata in enrichment_data.items():
            for tag_name, new_value in metadata.items():
                if tag_name in current_tags:
                    existing_value = current_tags[tag_name]
                    
                    # Prüfe ob Werte unterschiedlich sind
                    if not self._values_equal(existing_value, new_value):
                        # Konfidenz aus Metadaten extrahieren oder Standard verwenden
                        confidence = 0.8  # Standard-Confidence
                        if isinstance(metadata, dict) and '_confidence' in metadata:
                            confidence = metadata['_confidence']
                        
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

    def clear_user_preferences(self):
        """Löscht alle gespeicherten Benutzer-Präferenzen."""
        self.user_preferences.clear()
        self.batch_rules.clear()
        logger.info("Benutzer-Präferenzen gelöscht")
