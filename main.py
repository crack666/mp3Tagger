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
def test_connection(ctx):
    """Testet die Verbindung zu den konfigurierten APIs."""
    
    config: ConfigManager = ctx.obj['config']
    
    click.echo("Teste API-Verbindungen...")
    click.echo("(Diese Funktion wird in der nächsten Phase implementiert)")
    
    # TODO: Implementierung der API-Tests
    # - MusicBrainz Test-Anfrage
    # - Last.fm Test-Anfrage  
    # - Spotify Authentication Test
    # - YouTube API Test


if __name__ == '__main__':
    cli()
