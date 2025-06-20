# 🎵 MP3 Tagger

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Intelligente Metadaten-Anreicherung für MP3-Dateien mit mehreren APIs**

MP3 Tagger ist ein Python-Tool, das automatisch fehlende Metadaten für Ihre MP3-Sammlung ergänzt. Es kombiniert mehrere Musik-APIs und findet die besten YouTube-Videos basierend auf Klickzahlen.

## ✨ Features

- 🔍 **Intelligente Dateiname-Erkennung** - Automatisches Parsing von Künstler und Titel
- 🌐 **Multi-API-Integration** - MusicBrainz, Spotify, Last.fm, YouTube
- 🎥 **YouTube-Integration** - Automatische Verlinkung mit populärsten Videos
- 🛡️ **Tag-Schutz** - Bestehende Tags werden geschützt  
- 📊 **View-Count-Sortierung** - Findet die richtige Version mit den meisten Klicks
- ⚙️ **Konfigurierbarer Workflow** - Anpassbare Tag-Behandlung
- 💾 **Automatische Backups** - Sichere Tag-Updates

## 🚀 Quick Start

### Installation

```bash
# Repository klonen
git clone https://github.com/yourusername/mp3Tagger.git
cd mp3Tagger

# Dependencies installieren
pip install -r requirements.txt

# Oder mit dem Installer
./install.ps1  # Windows PowerShell
# oder
./install.bat  # Windows Batch
```

### API-Keys konfigurieren

```bash
# Setup-Assistent ausführen
python main.py setup-apis

# API-Keys in config/user_config.yaml eintragen
```

### Erste Schritte

```bash
# MP3-Verzeichnis scannen
python main.py scan ./my-music

# Einzelne Datei anreichern
python main.py enrich-single "song.mp3" --fetch-youtube --update-tags

# Ganzes Verzeichnis bearbeiten
python main.py enrich ./my-music --update-tags --fetch-youtube
```

## 📖 Kommandos

### Überblick

| Kommando | Beschreibung |
|----------|-------------|
| `scan` | Scannt Verzeichnis nach MP3s und zeigt Informationen |
| `enrich` | Reichert MP3s mit Metadaten an |
| `enrich-single` | Bearbeitet eine einzelne Datei |
| `info` | Zeigt Details zu einer MP3-Datei |
| `test-apis` | Testet API-Verbindungen |
| `setup-apis` | Hilfe bei der API-Konfiguration |
| `config-info` | Zeigt aktuelle Konfiguration |

### Detaillierte Kommandos

#### `scan` - Verzeichnis scannen
```bash
python main.py scan <verzeichnis> [optionen]
```

| Option | Beschreibung |
|--------|-------------|
| `--recursive, -r` | Unterverzeichnisse einschließen (Standard: true) |
| `--verbose, -v` | Detaillierte Ausgabe |

**Beispiele:**
```bash
# Scan mit Unterverzeichnissen
python main.py scan ./music --recursive

# Nur aktuelles Verzeichnis 
python main.py scan ./music --no-recursive
```

#### `enrich` - Metadaten anreichern
```bash
python main.py enrich <verzeichnis> [optionen]
```

| Option | Beschreibung |
|--------|-------------|
| `--update-tags` | Tags tatsächlich schreiben |
| `--fetch-youtube` | YouTube-Videos und Views abrufen |
| `--interactive, -i` | Interaktiver Konflikt-Modus |
| `--dry-run` | Vorschau ohne Änderungen |
| `--min-confidence <zahl>` | Mindest-Confidence (0-100) |

**Beispiele:**
```bash
# Vollständige Anreicherung mit YouTube
python main.py enrich ./music --update-tags --fetch-youtube

# Test-Lauf ohne Änderungen
python main.py enrich ./music --dry-run --fetch-youtube

# Interaktive Konfliktlösung
python main.py enrich ./music --interactive --update-tags
```

#### `enrich-single` - Einzelne Datei
```bash
python main.py enrich-single <datei> [optionen]
```

| Option | Beschreibung |
|--------|-------------|
| `--fetch-youtube` | YouTube-Daten abrufen |
| `--update-tags` | Tags aktualisieren |

**Beispiele:**
```bash
# Einzelne Datei mit YouTube-Daten
python main.py enrich-single "2Pac - California Love.mp3" --fetch-youtube --update-tags

# Nur Metadaten anzeigen
python main.py enrich-single "song.mp3" --fetch-youtube
```

#### `info` - Datei-Informationen
```bash
python main.py info <datei>
```

**Beispiel:**
```bash
python main.py info "music/song.mp3"
```

## ⚙️ Konfiguration

### API-Keys erforderlich

| Service | Kostenlos bis | Link |
|---------|---------------|------|
| 🎥 **YouTube Data API** | 10.000 Requests/Tag | [Google Cloud Console](https://console.cloud.google.com/) |
| 🎵 **Spotify Web API** | Unbegrenzt | [Spotify Developer](https://developer.spotify.com/dashboard) |
| 🎧 **Last.fm API** | 5.000 Requests/Stunde | [Last.fm API](https://www.last.fm/api/account/create) |

### Konfigurationsdatei
```yaml
# config/user_config.yaml
api_keys:
  youtube_api_key: "YOUR_YOUTUBE_API_KEY"
  spotify_client_id: "YOUR_SPOTIFY_CLIENT_ID"
  spotify_client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  lastfm_api_key: "YOUR_LASTFM_API_KEY"

matching_settings:
  min_confidence: 80        # Mindest-Confidence Score
  fuzzy_threshold: 0.8      # Fuzzy-Matching Schwellwert
  max_results_per_query: 10 # Max. Ergebnisse pro API-Anfrage
```

## 📊 Unterstützte Metadaten

### Standard-Tags
- **Basis**: Künstler, Titel, Album, Jahr, Genre, Track-Nummer
- **Erweitert**: Album-Künstler, Disc-Nummer, Dauer

### Custom YouTube-Tags
- `YOUTUBE_URL` - Link zum besten Video
- `YOUTUBE_VIEWS` - Anzahl Aufrufe
- `YOUTUBE_LIKES` - Anzahl Likes  
- `YOUTUBE_CHANNEL` - Kanal-Name

### Custom Spotify-Tags  
- `SPOTIFY_ID` - Spotify Track-ID
- `SPOTIFY_POPULARITY` - Popularity Score (0-100)
- `SPOTIFY_ARTIST_FOLLOWERS` - Künstler-Follower

### Custom Last.fm-Tags
- `LASTFM_PLAYCOUNT` - Anzahl Plays
- `LASTFM_LISTENERS` - Anzahl Hörer

## 🛡️ Sicherheit

- **Automatische Backups** vor jeder Tag-Änderung
- **Geschützte Tags** werden nie überschrieben
- **Confidence-basierte Updates** nur bei hoher Sicherheit
- **Dry-Run-Modus** zum sicheren Testen

## 📝 Beispiel-Output

```bash
$ python main.py enrich-single "2Pac & Dr. Dre - California Love.mp3" --fetch-youtube --update-tags

🎵 Datei: 2Pac & Dr. Dre - California Love.mp3
🎤 Künstler: 2Pac & Dr. Dre  
🎼 Titel: California Love

🔍 Suche Metadaten...
✓ 18 Ergebnisse gefunden
  1. musicbrainz: 2Pac & Dr. Dre - California Love (Confidence: 0.97)
  2. spotify: 2Pac - California Love (Confidence: 0.95)

🎥 Suche YouTube-Videos...  
  1. 2Pac ft. Dr. Dre - California Love (Official Video)
     Channel: UPROXX
     Views: 106.6M
     URL: https://www.youtube.com/watch?v=omfz62qu_Bc

✅ Tags erfolgreich aktualisiert!
```

## 🔧 Entwicklung

### Requirements
- Python 3.8+
- mutagen, requests, spotipy, aiohttp
- YouTube Data API v3, Spotify Web API, Last.fm API

### Tests
```bash
# API-Verbindungen testen
python main.py test-apis

# Konfiguration anzeigen  
python main.py config-info
```

## 📜 Lizenz

MIT License - siehe [LICENSE](LICENSE) für Details.

## 🤝 Beitragen

Contributions sind willkommen! Siehe [ROADMAP.md](ROADMAP.md) für geplante Features.

---

**Made with ❤️ for music lovers**
