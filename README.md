# MP3 Tagger - Intelligentes Metadaten-Anreicherungstool

Ein Python-basiertes Tool zur automatischen Anreicherung von MP3-Dateien mit Metadaten unter Verwendung verschiedener APIs und intelligenter Matching-Algorithmen.

## Überblick

Dieses Tool scannt MP3-Dateien in einem angegebenen Ordner und reichert sie mit fehlenden Metadaten an, ohne bereits vorhandene Tags zu überschreiben. Es bietet eine intelligente Konfliktauflösung und konfigurierbare Tag-Verwaltung.

## Hauptfunktionen

### Core Features
- **Automatische Metadaten-Erkennung**: Analyse von Dateinamen zur Extraktion von Künstler und Titel
- **API-Integration**: Nutzung mehrerer Musikdatenbanken für umfassende Metadaten
- **YouTube-Integration**: Automatische Verknüpfung mit YouTube-Videos und Abruf von Klickzahlen
- **Intelligenter Tag-Schutz**: Vorhandene Tags werden nicht überschrieben
- **Konflikt-Management**: Interaktive Auflösung bei abweichenden Daten
- **Konfigurierbare Tag-Verwaltung**: Flexible Einstellungen für zu verarbeitende Tags

### Metadaten-Kategorien
- **Basis-Tags**: Künstler, Titel, Album, Jahr, Genre
- **Erweiterte Tags**: YouTube-URL, Klickzahlen, Popularitätsscore
- **Technische Tags**: Bitrate, Dauer, Sample-Rate
- **Benutzer-Tags**: Benutzerdefinierte Felder (über Konfiguration)

## Technische Architektur

### 1. Datei-Scanner Modul (`file_scanner.py`)
```
Funktionen:
- Rekursive MP3-Datei-Erkennung
- Metadaten-Extraktion aus vorhandenen Tags
- Dateiname-Parsing für Künstler/Titel-Erkennung
- Dateisystem-Monitoring für neue Dateien
```

### 2. Metadaten-Resolver (`metadata_resolver.py`)
```
API-Integration:
- MusicBrainz API: Primäre Musikdatenbank
- Last.fm API: Genre-Informationen und zusätzliche Metadaten
- Spotify Web API: Alternative Datenquelle
- Discogs API: Detaillierte Veröffentlichungsinformationen

Matching-Algorithmus:
- Fuzzy String Matching für Künstler/Titel
- Phonetische Ähnlichkeit (Soundex/Metaphone)
- Levenshtein-Distanz für Titel-Matching
- Confidence-Score-Berechnung (0-100%)
```

### 3. YouTube-Integration (`youtube_handler.py`)
```
Features:
- YouTube Data API v3 Integration
- Automatische Video-Suche basierend auf Künstler + Titel
- Klickzahlen-Abruf und -Speicherung
- Video-URL-Extraktion
- Popularitätstrends-Tracking
```

### 4. Genre-Klassifikation (`genre_classifier.py`)
```
Funktionen:
- Multi-Genre-Unterstützung
- Genre-Hierarchie-Mapping
- Machine Learning basierte Genre-Vorhersage
- Genre-Confidence-Scoring
- Benutzer-Genre-Überschreibungen
```

### 5. Tag-Manager (`tag_manager.py`)
```
Verantwortlichkeiten:
- ID3v2.4 Tag-Manipulation
- Tag-Konflikt-Erkennung
- Backup-Erstellung vor Änderungen
- Batch-Tag-Updates
- Tag-Validierung und -Bereinigung
```

### 6. Konflikt-Resolver (`conflict_resolver.py`)
```
Features:
- Interaktive Konfliktauflösung
- Automatische Konfliktregeln
- Confidence-basierte Entscheidungen
- Benutzer-Präferenz-Speicherung
- Massenaktionen für ähnliche Konflikte
```

### 7. Konfigurationssystem (`config_manager.py`)
```yaml
# config.yaml Beispiel
api_keys:
  musicbrainz: "user-agent-string"
  lastfm: "api-key"
  spotify_client_id: "client-id"
  spotify_client_secret: "client-secret"
  youtube: "api-key"

tag_settings:
  protected_tags:
    - comment
    - user_defined_1
  processable_tags:
    - artist
    - title
    - album
    - date
    - genre
    - youtube_url
    - play_count
  auto_update_tags:
    - genre
    - date
  
matching_settings:
  min_confidence: 80
  fuzzy_threshold: 0.8
  max_results_per_query: 10
  
youtube_settings:
  search_format: "{artist} - {title} official"
  fallback_search: "{artist} {title}"
  min_view_count: 1000
```

## Implementierungsplan

### Phase 1: Grundgerüst (Woche 1-2)
1. **Projekt-Setup**
   - Python-Umgebung einrichten
   - Abhängigkeiten definieren (requirements.txt)
   - Grundlegende Projektstruktur erstellen

2. **Datei-Scanner implementieren**
   - MP3-Datei-Erkennung
   - Basis-Metadaten-Extraktion
   - Dateiname-Parsing

3. **Konfigurationssystem**
   - YAML-basierte Konfiguration
   - Validierung der Konfigurationsdatei
   - Standard-Konfiguration erstellen

### Phase 2: API-Integration (Woche 3-4)
1. **MusicBrainz Integration**
   - API-Client implementieren
   - Künstler/Album/Titel-Suche
   - Rate-Limiting beachten

2. **YouTube API Integration**
   - Video-Suche implementieren
   - Statistiken abrufen
   - URL-Generierung

3. **Matching-Algorithmus**
   - String-Ähnlichkeits-Funktionen
   - Confidence-Score-Berechnung
   - Multi-Source-Matching

### Phase 3: Tag-Management (Woche 5-6)
1. **ID3-Tag-Manipulation**
   - Sichere Tag-Updates
   - Backup-Mechanismus
   - Tag-Validierung

2. **Konflikt-Erkennung**
   - Vergleich vorhandener vs. neuer Daten
   - Konflikt-Kategorisierung
   - Automatische Auflösungsregeln

### Phase 4: Benutzerinteraktion (Woche 7-8)
1. **CLI-Interface**
   - Kommandozeilen-Parameter
   - Progress-Anzeige
   - Logging-System

2. **Interaktive Konfliktauflösung**
   - Benutzer-Prompts
   - Batch-Entscheidungen
   - Präferenz-Speicherung

### Phase 5: Erweiterte Features (Woche 9-10)
1. **Genre-Klassifikation**
   - Multi-API-Genre-Aggregation
   - ML-basierte Vorhersagen
   - Genre-Hierarchie-Mapping

2. **Performance-Optimierung**
   - Parallele API-Anfragen
   - Caching-Mechanismus
   - Batch-Processing

## Verwendete APIs und Bibliotheken

### APIs
- **MusicBrainz**: Primäre Musikdatenbank (kostenlos)
- **Last.fm**: Genre und Künstler-Informationen
- **YouTube Data API v3**: Video-Suche und Statistiken
- **Spotify Web API**: Alternative Metadaten-Quelle
- **Discogs API**: Detaillierte Veröffentlichungsinformationen

### Python-Bibliotheken
```
# Core Dependencies
mutagen          # ID3-Tag-Manipulation
requests         # HTTP-Anfragen
pyyaml          # Konfigurationsdateien
click           # CLI-Interface
tqdm            # Progress-Bars
fuzzywuzzy      # String-Matching
python-Levenshtein  # String-Distanz-Berechnung

# Optional Dependencies
spotipy         # Spotify API-Client
google-api-python-client  # YouTube API
discogs-client  # Discogs API
musicbrainzngs  # MusicBrainz API-Client
```

## Dateistruktur
```
mp3Tagger/
├── config/
│   ├── default_config.yaml
│   └── user_config.yaml
├── src/
│   ├── __init__.py
│   ├── file_scanner.py
│   ├── metadata_resolver.py
│   ├── youtube_handler.py
│   ├── genre_classifier.py
│   ├── tag_manager.py
│   ├── conflict_resolver.py
│   ├── config_manager.py
│   └── utils/
│       ├── __init__.py
│       ├── string_matching.py
│       └── api_helpers.py
├── tests/
│   ├── test_file_scanner.py
│   ├── test_metadata_resolver.py
│   └── test_integration.py
├── logs/
├── backups/
├── main.py
├── requirements.txt
├── setup.py
└── README.md
```

## Usage Examples

### Basis-Verwendung
```bash
python main.py --directory "C:\Music\MP3s" --config config/user_config.yaml
```

### Erweiterte Optionen
```bash
python main.py \
  --directory "C:\Music\MP3s" \
  --recursive \
  --min-confidence 85 \
  --backup-dir "C:\Music\Backups" \
  --log-level INFO \
  --interactive
```

### Batch-Modus (nicht-interaktiv)
```bash
python main.py \
  --directory "C:\Music\MP3s" \
  --batch-mode \
  --auto-resolve-conflicts \
  --confidence-threshold 90
```

## Herausforderungen und Lösungsansätze

### 1. Song-Matching-Genauigkeit
**Problem**: Dateinamen entsprechen nicht immer dem exakten Künstler-/Titel-Format
**Lösung**: 
- Multi-Level-Matching mit verschiedenen Parsing-Strategien
- Fuzzy-Matching mit konfigurierbaren Schwellenwerten
- Manual-Override für problematische Dateien

### 2. API-Rate-Limiting
**Problem**: Verschiedene APIs haben unterschiedliche Rate-Limits
**Lösung**:
- Intelligentes Rate-Limiting pro API
- Request-Caching zur Minimierung redundanter Anfragen
- Graceful Fallbacks zwischen APIs

### 3. Genre-Konsistenz
**Problem**: Verschiedene APIs verwenden unterschiedliche Genre-Klassifikationen
**Lösung**:
- Genre-Mapping-Tabellen zwischen APIs
- Gewichtete Genre-Aggregation
- Benutzer-konfigurierbare Genre-Präferenzen

### 4. YouTube-Matching-Genauigkeit
**Problem**: Falsche Videos können gematcht werden
**Lösung**:
- Multi-Parameter-Suche (Künstler + Titel + "official")
- View-Count-Mindestanzahl als Filter
- Titel-Ähnlichkeits-Prüfung für Suchergebnisse

## Qualitätssicherung

### Testing-Strategie
- Unit-Tests für alle Module
- Integration-Tests mit Mock-APIs
- End-to-End-Tests mit Beispiel-MP3s
- Performance-Tests mit großen Musiksammlungen

### Monitoring und Logging
- Detailliertes Logging aller API-Anfragen
- Erfolgs-/Fehlerstatistiken
- Performance-Metriken
- Benutzer-Aktions-Protokollierung

## Zukünftige Erweiterungen

### Phase 6: GUI-Interface
- Desktop-Anwendung mit tkinter/PyQt
- Drag-and-Drop-Funktionalität
- Visuelle Konfliktauflösung
- Batch-Operations-Dashboard

### Phase 7: Cloud-Integration
- Backup in Cloud-Storage
- Shared Metadaten-Cache
- Collaborative Tagging
- API-Key-Management-Service

### Phase 8: Machine Learning
- Personalisierte Genre-Klassifikation
- Automatische Konfliktauflösung basierend auf Benutzerverhalten
- Anomalie-Erkennung für fehlerhafte Metadaten
- Empfehlungssystem für ähnliche Künstler

## Getting Started

1. **Repository klonen**
2. **Abhängigkeiten installieren**: `pip install -r requirements.txt`
3. **API-Keys konfigurieren** in `config/user_config.yaml`
4. **Erstes Scan starten**: `python main.py --directory /path/to/mp3s --interactive`

## Lizenz

MIT License - Siehe LICENSE Datei für Details.