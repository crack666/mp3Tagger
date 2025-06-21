"""
CLI Scan Commands - Datei-Scanning und Informationen
"""

import click
import logging
import sys
from typing import Optional

from ..file_scanner import FileScanner


@click.command()
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
    
    config = ctx.obj['config']
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
        click.echo(f"Gefundene MP3-Dateien: {stats['total_files']}")
        click.echo(f"Gesamtgröße: {stats['total_size_mb']:.1f} MB")
        click.echo(f"Durchschnittliche Dateigröße: {stats['avg_size_mb']:.1f} MB")
        
        # Tag-Vollständigkeit
        tagged_files = stats['files_with_basic_tags']
        tag_percentage = (tagged_files / stats['total_files']) * 100
        click.echo(f"Dateien mit Basis-Tags: {tagged_files}/{stats['total_files']} ({tag_percentage:.1f}%)")
          # Details zu unvollständigen Tags
        incomplete_files = [f for f in mp3_files if not f.existing_tags]
        if incomplete_files and len(incomplete_files) <= 10:
            click.echo("\nDateien mit unvollständigen Tags:")
            for file_info in incomplete_files:
                click.echo(f"  • {file_info.file_path.name}")
        elif incomplete_files:
            click.echo(f"\nDateien mit unvollständigen Tags: {len(incomplete_files)} (zu viele zum Anzeigen)")
        
        # Empfehlungen
        if incomplete_files:
            click.echo(f"\n💡 Tipp: Verwenden Sie 'mp3tagger enrich \"{directory}\"' um fehlende Metadaten zu ergänzen.")
        
    except Exception as e:
        logger.error(f"Scan-Fehler: {e}")
        click.echo(f"Fehler beim Scannen: {e}", err=True)
        sys.exit(1)


@click.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def info(ctx, file_path: str):
    """Zeigt detaillierte Informationen über eine MP3-Datei an."""
    
    logger = logging.getLogger(__name__)
    
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3NoHeaderError
        import os
        
        # Dateigröße
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        
        click.echo("="*50)
        click.echo(f"DATEI-INFORMATIONEN")
        click.echo("="*50)
        click.echo(f"Pfad: {file_path}")
        click.echo(f"Größe: {file_size:.1f} MB")
        
        # MP3-Informationen laden
        try:
            audio = MP3(file_path)
            
            # Technische Informationen
            click.echo("\n" + "="*50)
            click.echo("TECHNISCHE INFORMATIONEN")
            click.echo("="*50)
            
            if audio.info:
                duration = audio.info.length
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                click.echo(f"Dauer: {minutes}:{seconds:02d}")
                click.echo(f"Bitrate: {audio.info.bitrate} kbps")
                click.echo(f"Sample Rate: {audio.info.sample_rate} Hz")
                click.echo(f"Channels: {audio.info.channels}")
                click.echo(f"Mode: {audio.info.mode}")
            
            # Tags anzeigen
            click.echo("\n" + "="*50)
            click.echo("METADATA-TAGS")
            click.echo("="*50)
            
            if audio.tags:
                # Standard-Tags
                standard_tags = {
                    'TIT2': 'Titel',
                    'TPE1': 'Künstler', 
                    'TALB': 'Album',
                    'TDRC': 'Jahr',
                    'TCON': 'Genre',
                    'TRCK': 'Track-Nummer',
                    'TPE2': 'Album-Künstler'
                }
                
                for tag_id, tag_name in standard_tags.items():
                    if tag_id in audio.tags:
                        value = str(audio.tags[tag_id][0])
                        click.echo(f"{tag_name}: {value}")
                
                # Custom Tags
                custom_found = False
                for tag_id in audio.tags:
                    if tag_id.startswith('TXXX:'):
                        if not custom_found:
                            click.echo(f"\nCustom Tags:")
                            custom_found = True
                        tag_name = tag_id[5:]  # Remove 'TXXX:' prefix
                        value = str(audio.tags[tag_id][0])
                        click.echo(f"  {tag_name}: {value}")
                
                # Alle verfügbaren Tags (für Debug)
                if ctx.obj.get('verbose', False):
                    click.echo(f"\nAlle verfügbaren Tags ({len(audio.tags)}):")
                    for tag_id in sorted(audio.tags.keys()):
                        try:
                            value = str(audio.tags[tag_id][0])
                            if len(value) > 50:
                                value = value[:47] + "..."
                            click.echo(f"  {tag_id}: {value}")
                        except:
                            click.echo(f"  {tag_id}: <Fehler beim Lesen>")
            else:
                click.echo("Keine ID3-Tags gefunden.")
                
        except ID3NoHeaderError:
            click.echo("Keine ID3-Tags in der Datei gefunden.")
        except Exception as e:
            click.echo(f"Fehler beim Lesen der MP3-Datei: {e}", err=True)
            
    except Exception as e:
        logger.error(f"Info-Fehler: {e}")
        click.echo(f"Fehler beim Analysieren der Datei: {e}", err=True)
        sys.exit(1)
