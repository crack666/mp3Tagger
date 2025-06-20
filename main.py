"""
MP3 Tagger - Hauptprogramm

Kommandozeilen-Interface für das MP3-Tagging-Tool.
"""

import click
import logging
import sys
from pathlib import Path
from typing import Optional

# Lokale Imports
from src.config_manager import get_config, ConfigManager
from src.file_scanner import FileScanner
from src.metadata_resolver import MetadataResolver
from src.youtube_handler import YouTubeHandler, MultiPlatformVideoHandler
from src.tag_manager import TagManager
from src.conflict_resolver import ConflictResolver


def setup_cli_logging(verbose: bool = False):
    """Konfiguriert das Logging für die Kommandozeile."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Einfacher Formatter für CLI
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Root Logger konfigurieren
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # CLI Handler hinzufügen (zusätzlich zu Config-Handlers)
    logger.addHandler(console_handler)


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Pfad zur Konfigurationsdatei')
@click.option('--verbose', '-v', is_flag=True, 
              help='Ausführliche Ausgabe aktivieren')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """MP3 Tagger - Intelligentes Metadaten-Anreicherungstool."""
    ctx.ensure_object(dict)
    
    # Logging konfigurieren
    setup_cli_logging(verbose)
    
    try:
        # Konfiguration laden
        ctx.obj['config'] = get_config(config)
        ctx.obj['verbose'] = verbose
        
        logger = logging.getLogger(__name__)
        logger.info("MP3 Tagger gestartet")
        
    except Exception as e:
        click.echo(f"Fehler beim Laden der Konfiguration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--recursive', '-r', is_flag=True, default=True,
              help='Unterverzeichnisse einschließen')
@click.option('--dry-run', is_flag=True,
              help='Nur anzeigen was getan würde, ohne Änderungen')
@click.option('--interactive', '-i', is_flag=True,
              help='Interaktiver Modus für Konflikte')
@click.option('--min-confidence', type=int, default=None,
              help='Mindest-Confidence-Score für automatische Updates')
@click.pass_context
def scan(ctx, directory: str, recursive: bool, dry_run: bool, 
         interactive: bool, min_confidence: Optional[int]):
    """Scannt ein Verzeichnis nach MP3-Dateien und zeigt Informationen an."""
    
    config: ConfigManager = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    try:
        # File Scanner initialisieren
        scanner = FileScanner()
        
        # Verzeichnis scannen
        click.echo(f"Scanne Verzeichnis: {directory}")
        click.echo(f"Rekursiv: {'Ja' if recursive else 'Nein'}")
        
        with click.progressbar(length=100, label='Scanne Dateien...') as bar:
            mp3_files = scanner.scan_directory(directory, recursive)
            bar.update(100)
        
        if not mp3_files:
            click.echo("Keine MP3-Dateien gefunden.")
            return
        
        # Statistiken anzeigen
        stats = scanner.get_file_stats(mp3_files)
        
        click.echo("\n" + "="*50)
        click.echo("SCAN-ERGEBNISSE")
        click.echo("="*50)
        click.echo(f"Gefundene Dateien: {stats['total_files']}")
        click.echo(f"Gesamtgröße: {stats['total_size_mb']} MB")
        click.echo(f"Gesamtdauer: {stats['total_duration_minutes']} Minuten")
        click.echo(f"Erfolgreich geparst: {stats['parsed_files']}")
        click.echo(f"Mit vorhandenen Tags: {stats['files_with_tags']}")
        click.echo(f"Durchschnittliche Bitrate: {stats['avg_bitrate']} kbps")
        click.echo(f"Durchschnittliche Parse-Confidence: {stats['avg_confidence']:.2f}")
        
        # Detaillierte Dateiinformationen anzeigen
        if ctx.obj['verbose']:
            click.echo("\n" + "="*50)
            click.echo("DETAILLIERTE DATEIINFORMATIONEN")
            click.echo("="*50)
            
            for i, mp3_file in enumerate(mp3_files[:10]):  # Nur erste 10 anzeigen
                click.echo(f"\n{i+1}. {mp3_file.file_path.name}")
                click.echo(f"   Größe: {mp3_file.file_size // 1024} KB")
                click.echo(f"   Dauer: {mp3_file.duration:.1f}s")
                click.echo(f"   Bitrate: {mp3_file.bitrate} kbps")
                
                if mp3_file.parsed_artist and mp3_file.parsed_title:
                    click.echo(f"   Geparst: {mp3_file.parsed_artist} - {mp3_file.parsed_title}")
                    click.echo(f"   Confidence: {mp3_file.confidence:.2f}")
                else:
                    click.echo(f"   Parsing fehlgeschlagen")
                
                if mp3_file.existing_tags:
                    click.echo(f"   Vorhandene Tags: {', '.join(mp3_file.existing_tags.keys())}")
                else:
                    click.echo(f"   Keine Tags vorhanden")
            
            if len(mp3_files) > 10:
                click.echo(f"\n... und {len(mp3_files) - 10} weitere Dateien")
        
        # Problematische Dateien anzeigen
        problematic_files = [f for f in mp3_files if not f.parsed_artist or not f.parsed_title]
        if problematic_files:
            click.echo(f"\n⚠️  {len(problematic_files)} Dateien konnten nicht geparst werden:")
            for pf in problematic_files[:5]:  # Nur erste 5 anzeigen
                click.echo(f"   - {pf.file_path.name}")
            if len(problematic_files) > 5:
                click.echo(f"   ... und {len(problematic_files) - 5} weitere")
        
    except Exception as e:
        logger.error(f"Fehler beim Scannen: {e}")
        click.echo(f"Fehler beim Scannen: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def info(ctx, file_path: str):
    """Zeigt detaillierte Informationen über eine MP3-Datei an."""
    
    logger = logging.getLogger(__name__)
    
    try:
        scanner = FileScanner()
        mp3_info = scanner.scan_single_file(file_path)
        
        if not mp3_info:
            click.echo("Datei konnte nicht verarbeitet werden.", err=True)
            return
        
        click.echo("="*60)
        click.echo(f"DATEI-INFORMATIONEN: {mp3_info.file_path.name}")
        click.echo("="*60)
        
        # Basis-Informationen
        click.echo(f"Pfad: {mp3_info.file_path}")
        click.echo(f"Größe: {mp3_info.file_size // 1024} KB")
        click.echo(f"Dauer: {mp3_info.duration:.1f} Sekunden")
        click.echo(f"Bitrate: {mp3_info.bitrate} kbps")
        click.echo(f"Sample Rate: {mp3_info.sample_rate} Hz")
        
        # Parsing-Ergebnisse
        click.echo("\n" + "-"*30)
        click.echo("DATEINAME-PARSING")
        click.echo("-"*30)
        
        if mp3_info.parsed_artist and mp3_info.parsed_title:
            click.echo(f"Künstler: {mp3_info.parsed_artist}")
            click.echo(f"Titel: {mp3_info.parsed_title}")
            click.echo(f"Confidence: {mp3_info.confidence:.2f}")
        else:
            click.echo("Dateiname konnte nicht geparst werden")
        
        # Vorhandene Tags
        click.echo("\n" + "-"*30)
        click.echo("VORHANDENE TAGS")
        click.echo("-"*30)
        
        if mp3_info.existing_tags:
            for tag, value in mp3_info.existing_tags.items():
                if value:  # Nur nicht-leere Werte anzeigen
                    click.echo(f"{tag}: {value}")
        else:
            click.echo("Keine Tags vorhanden")
        
    except Exception as e:
        logger.error(f"Fehler beim Analysieren der Datei: {e}")
        click.echo(f"Fehler: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def config_info(ctx):
    """Zeigt die aktuelle Konfiguration an."""
    
    config: ConfigManager = ctx.obj['config']
    
    click.echo("="*50)
    click.echo("KONFIGURATIONSINFORMATIONEN")
    click.echo("="*50)
    
    # Konfigurationsdateien
    click.echo(f"Standard-Konfiguration: {config.default_config_path}")
    click.echo(f"Benutzer-Konfiguration: {config.user_config_path}")
    click.echo(f"Benutzer-Config existiert: {'Ja' if config.user_config_path.exists() else 'Nein'}")
    
    # API-Schlüssel Status
    click.echo("\n" + "-"*30)
    click.echo("API-SCHLÜSSEL STATUS")
    click.echo("-"*30)
    
    api_services = [
        ('lastfm_api_key', 'Last.fm'),
        ('spotify_client_id', 'Spotify'),
        ('youtube_api_key', 'YouTube'),
        ('discogs_user_token', 'Discogs')
    ]
    
    for key, service in api_services:
        api_key = config.get_api_key(key)
        status = "✓ Konfiguriert" if api_key else "✗ Nicht konfiguriert"
        click.echo(f"{service}: {status}")
    
    # Wichtige Einstellungen
    click.echo("\n" + "-"*30)
    click.echo("WICHTIGE EINSTELLUNGEN")
    click.echo("-"*30)
    
    click.echo(f"Min. Confidence: {config.get('matching_settings.min_confidence')}")
    click.echo(f"Fuzzy Threshold: {config.get('matching_settings.fuzzy_threshold')}")
    click.echo(f"Log Level: {config.get('logging.level')}")
    click.echo(f"Auto-Backup: {config.get('backup.auto_backup')}")
    
    # Geschützte Tags
    protected_tags = config.get('tag_settings.protected_tags', [])
    click.echo(f"\nGeschützte Tags ({len(protected_tags)}): {', '.join(protected_tags)}")


@cli.command()
@click.pass_context  
def create_config(ctx):
    """Erstellt eine Benutzer-Konfigurationsvorlage."""
    
    config: ConfigManager = ctx.obj['config']
    
    try:
        config.create_user_config_template()
        click.echo("✓ Benutzer-Konfigurationsvorlage erstellt")
        click.echo(f"Pfad: {config.user_config_path}")
        click.echo("\nBitte fügen Sie Ihre API-Schlüssel in die Datei ein.")
        
    except Exception as e:
        click.echo(f"Fehler beim Erstellen der Konfiguration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def test_apis(ctx):
    """Testet die Verbindung zu den konfigurierten APIs."""
    
    config: ConfigManager = ctx.obj['config']
    
    click.echo("🧪 Teste API-Verbindungen...")
    click.echo("=" * 40)
    
    try:
        # Metadata Resolver testen
        metadata_resolver = MetadataResolver()
        api_status = metadata_resolver.get_api_status()
        
        click.echo("📊 Metadaten-APIs:")
        for api, available in api_status.items():
            status = "✓" if available else "✗"
            click.echo(f"  {status} {api.capitalize()}: {'Verfügbar' if available else 'Nicht konfiguriert'}")
        
        # YouTube API testen
        youtube_handler = YouTubeHandler()
        youtube_available = youtube_handler.is_api_available()
        status = "✓" if youtube_available else "✗"
        click.echo(f"  {status} YouTube: {'Verfügbar' if youtube_available else 'Nicht konfiguriert'}")
        
        # Test-Anfragen (falls APIs verfügbar)
        if any(api_status.values()) or youtube_available:
            click.echo("\n🔍 Führe Test-Anfragen durch...")
            
            test_artist = "2Pac"
            test_title = "California Love"
            
            # Metadaten-Test
            if any(api_status.values()):
                import asyncio
                try:
                    results = asyncio.run(
                        metadata_resolver.resolve_metadata(test_artist, test_title)
                    )
                    click.echo(f"  ✓ Metadaten-Test: {len(results)} Ergebnisse für '{test_artist} - {test_title}'")
                except Exception as e:
                    click.echo(f"  ✗ Metadaten-Test fehlgeschlagen: {e}")
            
            # YouTube-Test
            if youtube_available:
                try:
                    videos = asyncio.run(
                        youtube_handler.find_videos(test_artist, test_title)
                    )
                    click.echo(f"  ✓ YouTube-Test: {len(videos)} Videos gefunden")
                except Exception as e:
                    click.echo(f"  ✗ YouTube-Test fehlgeschlagen: {e}")
        
        click.echo("\n💡 Hinweise:")
        if not any(api_status.values()) and not youtube_available:
            click.echo("  - Keine APIs konfiguriert!")
            click.echo("  - Bitte API-Keys in config/user_config.yaml eintragen")
            click.echo("  - Verwenden Sie 'python main.py setup-apis' für Hilfe")
        else:
            click.echo("  - Mindestens eine API ist verfügbar ✓")
            click.echo("  - Sie können mit der Metadaten-Anreicherung beginnen!")
        
    except Exception as e:
        click.echo(f"Fehler beim Testen der APIs: {e}", err=True)


@cli.command()
@click.pass_context
def setup_apis(ctx):
    """Hilfsprogramm zum Einrichten der API-Keys."""
    
    click.echo("🔧 API-Setup-Assistent")
    click.echo("=" * 30)
    
    click.echo("\nFür die volle Funktionalität benötigen Sie API-Keys von folgenden Diensten:")
    
    click.echo("\n1. 📺 YouTube Data API v3 (Google Cloud Console)")
    click.echo("   - Kostenlos bis zu 10.000 Anfragen/Tag")
    click.echo("   - Anmeldung: https://console.cloud.google.com/")
    click.echo("   - Aktivieren Sie die 'YouTube Data API v3'")
    click.echo("   - Erstellen Sie Anmeldedaten (API-Key)")
    
    click.echo("\n2. 🎵 Spotify Web API")
    click.echo("   - Kostenlos für nicht-kommerzielle Nutzung")
    click.echo("   - Anmeldung: https://developer.spotify.com/dashboard")
    click.echo("   - Erstellen Sie eine neue App")
    click.echo("   - Kopieren Sie Client ID und Client Secret")
    
    click.echo("\n3. 🎧 Last.fm API")
    click.echo("   - Kostenlos für nicht-kommerzielle Nutzung")
    click.echo("   - Anmeldung: https://www.last.fm/api/account/create")
    click.echo("   - API-Key ist kostenlos verfügbar")
    
    click.echo("\n4. 💿 Discogs API (optional)")
    click.echo("   - Kostenlos für begrenzte Nutzung")
    click.echo("   - Anmeldung: https://www.discogs.com/settings/developers")
    
    config_path = Path("config/user_config.yaml")
    
    click.echo(f"\n📝 Konfigurationsdatei: {config_path}")
    
    if config_path.exists():
        click.echo("✓ Datei existiert bereits")
        if click.confirm("Möchten Sie die aktuelle Konfiguration anzeigen?"):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                click.echo("\nAktuelle Konfiguration:")
                click.echo("-" * 30)
                click.echo(content)
    else:
        click.echo("✗ Datei nicht gefunden")
        if click.confirm("Möchten Sie eine Vorlage erstellen?"):
            ctx.invoke(create_config)
    
    click.echo("\n🚀 Nach dem Einrichten der API-Keys:")
    click.echo("1. Testen Sie die Verbindung: python main.py test-apis")
    click.echo("2. Scannen Sie Ihre Musik: python main.py scan ./mp3s")
    click.echo("3. Reichern Sie Metadaten an: python main.py enrich ./mp3s --update-tags --fetch-youtube")


@cli.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--recursive', '-r', is_flag=True, default=True,
              help='Unterverzeichnisse einschließen')
@click.option('--dry-run', is_flag=True,
              help='Nur anzeigen was getan würde, ohne Änderungen')
@click.option('--interactive', '-i', is_flag=True,
              help='Interaktiver Modus für Konflikte')
@click.option('--min-confidence', type=int, default=None,
              help='Mindest-Confidence-Score für automatische Updates')
@click.option('--update-tags', is_flag=True,
              help='Tags mit gefundenen Metadaten aktualisieren')
@click.option('--fetch-youtube', is_flag=True,
              help='YouTube-Videos und Statistiken abrufen')
@click.pass_context
def enrich(ctx, directory: str, recursive: bool, dry_run: bool, 
          interactive: bool, min_confidence: Optional[int], 
          update_tags: bool, fetch_youtube: bool):
    """Reichert MP3-Dateien mit Metadaten aus verschiedenen APIs an."""
    
    config: ConfigManager = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    try:
        # API-Handler initialisieren
        metadata_resolver = MetadataResolver()
        youtube_handler = MultiPlatformVideoHandler()
        tag_manager = TagManager()
        conflict_resolver = ConflictResolver()
        
        # API-Status prüfen
        api_status = metadata_resolver.get_api_status()
        click.echo("API-Status:")
        for api, available in api_status.items():
            status = "✓ Verfügbar" if available else "✗ Nicht konfiguriert"
            click.echo(f"  {api}: {status}")
        
        if not any(api_status.values()):
            click.echo("⚠️  Keine APIs konfiguriert! Bitte API-Keys in user_config.yaml eintragen.")
            return
        
        # File Scanner initialisieren
        scanner = FileScanner()
        
        click.echo(f"\nScanne Verzeichnis: {directory}")
        with click.progressbar(length=100, label='Scanne Dateien...') as bar:
            mp3_files = scanner.scan_directory(directory, recursive)
            bar.update(100)
        
        if not mp3_files:
            click.echo("Keine MP3-Dateien gefunden.")
            return
        
        # Mindest-Confidence aus Konfiguration oder Parameter
        if min_confidence is None:
            min_confidence = config.get('matching_settings.min_confidence', 80)
        min_confidence_float = min_confidence / 100.0
        
        processed_count = 0
        updated_count = 0
        conflict_count = 0
        
        # Lade gespeicherte Benutzer-Präferenzen
        if interactive:
            conflict_resolver.load_user_preferences()
        
        click.echo(f"\n🔍 Verarbeite {len(mp3_files)} Dateien...")
        
        for i, mp3_file in enumerate(mp3_files):
            click.echo(f"\n[{i+1}/{len(mp3_files)}] {mp3_file.file_path.name}")
            
            # Prüfe ob bereits Metadaten vorhanden sind
            if not mp3_file.parsed_artist or not mp3_file.parsed_title:
                click.echo("  ⚠️  Dateiname konnte nicht geparst werden - überspringe")
                continue
            
            try:
                # Metadaten von APIs abrufen
                click.echo(f"  🔍 Suche Metadaten für: {mp3_file.parsed_artist} - {mp3_file.parsed_title}")
                
                import asyncio
                metadata_results = asyncio.run(
                    metadata_resolver.resolve_metadata(
                        mp3_file.parsed_artist, 
                        mp3_file.parsed_title
                    )
                )
                
                if not metadata_results:
                    click.echo("  ❌ Keine Metadaten gefunden")
                    continue
                
                # Beste Metadaten zusammenführen
                merged_metadata = metadata_resolver.merge_metadata_results(
                    metadata_results, min_confidence_float
                )
                
                if not merged_metadata:
                    click.echo("  ❌ Keine ausreichend vertrauenswürdigen Metadaten gefunden")
                    continue
                
                click.echo(f"  ✓ Metadaten gefunden (Confidence: {merged_metadata.get('confidence', 0):.2f})")
                click.echo(f"    Quelle: {merged_metadata.get('primary_source', 'unknown')}")
                
                # YouTube-Videos abrufen (optional)
                if fetch_youtube and youtube_handler.youtube_handler.is_api_available():
                    click.echo("  🎥 Suche YouTube-Videos...")
                    
                    video_results = asyncio.run(
                        youtube_handler.find_all_videos(
                            mp3_file.parsed_artist,
                            mp3_file.parsed_title
                        )
                    )
                    
                    if video_results:
                        best_video = youtube_handler.get_best_video(video_results)
                        if best_video:
                            # YouTube-Daten zu Metadaten hinzufügen
                            merged_metadata.update({
                                'youtube_url': best_video.url,
                                'youtube_video_id': best_video.video_id,
                                'youtube_views': best_video.view_count,
                                'youtube_likes': best_video.like_count,
                                'youtube_channel': best_video.channel,
                                'youtube_published': best_video.published_date
                            })
                            
                            view_count_formatted = youtube_handler.youtube_handler.format_view_count(
                                best_video.view_count
                            )
                            click.echo(f"    ✓ YouTube: {best_video.title} ({view_count_formatted} Views)")
                
                # Konflikte analysieren
                conflicts = conflict_resolver.analyze_conflicts(
                    mp3_file.existing_tags,
                    merged_metadata,
                    merged_metadata.get('confidence', 0),
                    merged_metadata.get('primary_source', 'unknown')
                )
                
                if conflicts:
                    conflict_count += len(conflicts)
                    click.echo(f"  ⚠️  {len(conflicts)} Konflikte gefunden")
                    
                    if dry_run:
                        # Nur anzeigen, nicht ändern
                        for conflict in conflicts:
                            click.echo(f"    {conflict.tag_name}: '{conflict.existing_value}' → '{conflict.new_value}'")
                        continue
                    
                    # Konflikte auflösen
                    if interactive:
                        resolutions = conflict_resolver.resolve_conflicts_interactive(
                            conflicts, str(mp3_file.file_path)
                        )
                    else:
                        resolutions = conflict_resolver.resolve_conflicts_automatic(conflicts)
                    
                    # Auflösungen anwenden
                    for tag_name, resolution in resolutions.items():
                        merged_metadata[tag_name] = resolution.final_value
                
                # Tags schreiben (falls gewünscht)
                if update_tags and not dry_run:
                    # Endgültige Tags zusammenführen
                    final_tags = tag_manager.merge_tags(
                        mp3_file.existing_tags,
                        merged_metadata
                    )
                    
                    success = tag_manager.write_tags(
                        mp3_file.file_path,
                        final_tags,
                        create_backup=True
                    )
                    
                    if success:
                        updated_count += 1
                        click.echo("  ✅ Tags erfolgreich aktualisiert")
                    else:
                        click.echo("  ❌ Fehler beim Schreiben der Tags")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Fehler bei der Verarbeitung von {mp3_file.file_path}: {e}")
                click.echo(f"  ❌ Fehler: {e}")
                continue
        
        # Zusammenfassung
        click.echo("\n" + "="*60)
        click.echo("ZUSAMMENFASSUNG")
        click.echo("="*60)
        click.echo(f"Verarbeitete Dateien: {processed_count}/{len(mp3_files)}")
        if update_tags and not dry_run:
            click.echo(f"Aktualisierte Dateien: {updated_count}")
        click.echo(f"Konflikte gefunden: {conflict_count}")
        
        if dry_run:
            click.echo("\n💡 Dies war ein Testlauf. Verwenden Sie --update-tags zum tatsächlichen Aktualisieren.")
        
        # Benutzer-Präferenzen speichern
        if interactive and conflict_resolver.user_preferences:
            conflict_resolver.save_user_preferences()
            click.echo("✓ Benutzer-Präferenzen für zukünftige Läufe gespeichert")
        
    except Exception as e:
        logger.error(f"Fehler bei der Metadaten-Anreicherung: {e}")
        click.echo(f"Fehler: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--fetch-youtube', is_flag=True, help='YouTube-Videos abrufen')
@click.option('--update-tags', is_flag=True, help='Tags aktualisieren')
@click.pass_context
def enrich_single(ctx, file_path: str, fetch_youtube: bool, update_tags: bool):
    """Reichert eine einzelne MP3-Datei mit Metadaten an."""
    
    config: ConfigManager = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    try:
        # Scanner und APIs initialisieren
        scanner = FileScanner()
        metadata_resolver = MetadataResolver()
        youtube_handler = MultiPlatformVideoHandler()
        tag_manager = TagManager()
        
        # Datei analysieren
        mp3_info = scanner.scan_single_file(file_path)
        if not mp3_info:
            click.echo("Datei konnte nicht verarbeitet werden.", err=True)
            return
        
        if not mp3_info.parsed_artist or not mp3_info.parsed_title:
            click.echo("Dateiname konnte nicht geparst werden.", err=True)
            return
        
        click.echo(f"🎵 Datei: {mp3_info.file_path.name}")
        click.echo(f"🎤 Künstler: {mp3_info.parsed_artist}")
        click.echo(f"🎼 Titel: {mp3_info.parsed_title}")
        
        # Metadaten abrufen
        click.echo("\n🔍 Suche Metadaten...")
        import asyncio
        metadata_results = asyncio.run(
            metadata_resolver.resolve_metadata(
                mp3_info.parsed_artist,
                mp3_info.parsed_title
            )
        )
        
        if metadata_results:
            click.echo(f"✓ {len(metadata_results)} Ergebnisse gefunden")
            
            # Beste Ergebnisse anzeigen
            for i, result in enumerate(metadata_results[:3], 1):
                click.echo(f"  {i}. {result.source}: {result.artist} - {result.title}")
                click.echo(f"     Confidence: {result.confidence:.2f}")
                if result.genres:
                    click.echo(f"     Genres: {', '.join(result.genres)}")
        
        # YouTube-Videos (optional)
        if fetch_youtube and youtube_handler.youtube_handler.is_api_available():
            click.echo("\n🎥 Suche YouTube-Videos...")
            video_results = asyncio.run(
                youtube_handler.find_all_videos(
                    mp3_info.parsed_artist,
                    mp3_info.parsed_title
                )
            )
            
            if video_results and 'youtube' in video_results:
                youtube_videos = video_results['youtube'][:3]  # Top 3
                for i, video in enumerate(youtube_videos, 1):
                    view_count = youtube_handler.youtube_handler.format_view_count(video.view_count)
                    click.echo(f"  {i}. {video.title}")
                    click.echo(f"     Channel: {video.channel}")
                    click.echo(f"     Views: {view_count}")
                    click.echo(f"     URL: {video.url}")
        
        # Tags aktualisieren (optional)
        if update_tags and metadata_results:
            min_confidence = config.get('matching_settings.min_confidence', 80) / 100
            merged_metadata = metadata_resolver.merge_metadata_results(
                metadata_results, min_confidence
            )
            
            if merged_metadata:
                success = tag_manager.write_tags(
                    mp3_info.file_path,
                    merged_metadata,
                    create_backup=True
                )
                
                if success:
                    click.echo("\n✅ Tags erfolgreich aktualisiert!")
                else:
                    click.echo("\n❌ Fehler beim Aktualisieren der Tags!")
        
    except Exception as e:
        logger.error(f"Fehler bei der Datei-Anreicherung: {e}")
        click.echo(f"Fehler: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
