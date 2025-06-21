"""
CLI Enrich Commands - Metadaten-Anreicherung
"""

import click
import logging
import sys
import asyncio
from typing import Optional
from pathlib import Path

from ..file_scanner import FileScanner
from ..metadata_resolver import MetadataResolver
from ..youtube_handler import YouTubeHandler, MultiPlatformVideoHandler
from ..tag_manager import TagManager
from ..conflict_resolver import ConflictResolver


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
@click.option('--update-tags', is_flag=True,
              help='Tags mit gefundenen Metadaten aktualisieren')
@click.option('--fetch-youtube', is_flag=True,
              help='YouTube-Videos und Statistiken abrufen')
@click.pass_context
def enrich(ctx, directory: str, recursive: bool, dry_run: bool, 
          interactive: bool, min_confidence: Optional[int], 
          update_tags: bool, fetch_youtube: bool):
    """Reichert MP3-Dateien mit Metadaten aus verschiedenen APIs an."""
    
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    try:
        # API-Handler initialisieren
        metadata_resolver = MetadataResolver(config)
        youtube_handler = MultiPlatformVideoHandler(config)
        tag_manager = TagManager(config)
        conflict_resolver = ConflictResolver(config)
        
        # API-Status prüfen
        api_status = metadata_resolver.get_api_status()
        enabled_apis = [api for api, status in api_status.items() if status]
        
        if not enabled_apis:
            click.echo("⚠ Keine APIs aktiviert. Verwenden Sie 'mp3tagger setup-apis' zur Konfiguration.", err=True)
            sys.exit(1)
        
        click.echo(f"Aktive APIs: {', '.join(enabled_apis)}")
        
        # Dateien scannen
        scanner = FileScanner()
        click.echo(f"Scanne Verzeichnis: {directory}")
        
        with click.progressbar(length=100, label='Scanne Dateien...') as bar:
            mp3_files = scanner.scan_directory(directory, recursive)
            bar.update(100)
        
        if not mp3_files:
            click.echo("Keine MP3-Dateien gefunden.")
            return
        
        click.echo(f"Gefundene MP3-Dateien: {len(mp3_files)}")
        
        if dry_run:
            click.echo("\n🔍 DRY-RUN Modus - Keine Änderungen werden vorgenommen!")
        
        # Async-Verarbeitung
        async def process_files():
            results = {
                'processed': 0,
                'enriched': 0,
                'skipped': 0,
                'errors': 0
            }
            
            # Progress Bar für Verarbeitung
            with click.progressbar(mp3_files, label='Verarbeite Dateien...') as files:
                for file_path in files:
                    try:
                        # Aktuelle Tags laden
                        current_tags = tag_manager.read_tags(file_path)
                        results['processed'] += 1
                        
                        # Basis-Informationen für Suche
                        search_artist = current_tags.get('TPE1', [''])[0] if 'TPE1' in current_tags else ''
                        search_title = current_tags.get('TIT2', [''])[0] if 'TIT2' in current_tags else ''
                        
                        if not search_artist and not search_title:
                            # Versuche aus Dateiname zu extrahieren
                            from ..utils.string_matching import extract_artist_title_from_filename
                            extracted = extract_artist_title_from_filename(file_path.name)
                            if extracted:
                                search_artist, search_title = extracted
                        
                        if not search_artist or not search_title:
                            click.echo(f"⚠ Überspringe {file_path.name}: Unzureichende Informationen")
                            results['skipped'] += 1
                            continue
                        
                        # Metadaten sammeln
                        enrichment_data = {}
                        
                        # Standard-APIs durchsuchen
                        if 'musicbrainz' in enabled_apis:
                            mb_results = await metadata_resolver.search_musicbrainz(search_artist, search_title)
                            if mb_results:
                                enrichment_data['musicbrainz'] = mb_results[0]  # Bestes Ergebnis
                        
                        if 'spotify' in enabled_apis:
                            spotify_results = await metadata_resolver.search_spotify(search_artist, search_title)
                            if spotify_results:
                                enrichment_data['spotify'] = spotify_results[0]
                        
                        if 'lastfm' in enabled_apis:
                            lastfm_results = await metadata_resolver.search_lastfm(search_artist, search_title)
                            if lastfm_results:
                                enrichment_data['lastfm'] = lastfm_results
                        
                        # YouTube-Videos abrufen (falls gewünscht)
                        if fetch_youtube and 'youtube' in enabled_apis:
                            try:
                                youtube_results = await youtube_handler.search_videos(f"{search_artist} {search_title}")
                                if youtube_results:
                                    # Bestes Video (höchste Klickzahl)
                                    best_video = max(youtube_results, key=lambda v: v.get('view_count', 0))
                                    enrichment_data['youtube'] = best_video
                            except Exception as e:
                                logger.debug(f"YouTube-Fehler für {file_path.name}: {e}")
                        
                        # Anreicherung durchführen, wenn Daten gefunden
                        if enrichment_data:
                            # Konflikte auflösen
                            resolved_tags = conflict_resolver.resolve_metadata_conflicts(
                                current_tags, enrichment_data
                            )
                            
                            if interactive:
                                # Interaktive Bestätigung (vereinfacht)
                                changes = []
                                for tag_id, new_value in resolved_tags.items():
                                    if tag_id not in current_tags or str(current_tags[tag_id][0]) != str(new_value):
                                        old_value = str(current_tags[tag_id][0]) if tag_id in current_tags else 'Leer'
                                        changes.append(f"  {tag_id}: {old_value} → {new_value}")
                                
                                if changes:
                                    click.echo(f"\nVorgeschlagene Änderungen für {file_path.name}:")
                                    for change in changes[:5]:  # Max 5 anzeigen
                                        click.echo(change)
                                    if len(changes) > 5:
                                        click.echo(f"  ... und {len(changes)-5} weitere")
                                    
                                    if not click.confirm("Änderungen übernehmen?"):
                                        results['skipped'] += 1
                                        continue
                            
                            # Tags schreiben (falls nicht dry-run)
                            if not dry_run and update_tags:
                                tag_manager.write_tags(file_path, resolved_tags)
                                click.echo(f"✓ Angereichert: {file_path.name}")
                            elif dry_run:
                                click.echo(f"🔍 Würde anreichern: {file_path.name}")
                            
                            results['enriched'] += 1
                        else:
                            click.echo(f"ℹ Keine Anreicherung: {file_path.name}")
                            results['skipped'] += 1
                            
                    except Exception as e:
                        logger.error(f"Fehler bei {file_path.name}: {e}")
                        results['errors'] += 1
            
            return results
        
        # Async-Verarbeitung starten
        results = asyncio.run(process_files())
        
        # Ergebnisse anzeigen
        click.echo("\n" + "="*50)
        click.echo("ANREICHERUNGS-ERGEBNISSE")
        click.echo("="*50)
        click.echo(f"Verarbeitete Dateien: {results['processed']}")
        click.echo(f"Angereicherte Dateien: {results['enriched']}")
        click.echo(f"Übersprungene Dateien: {results['skipped']}")
        click.echo(f"Fehler: {results['errors']}")
        
        if dry_run and results['enriched'] > 0:
            click.echo(f"\n💡 Verwenden Sie --update-tags um die Änderungen tatsächlich anzuwenden.")
        
    except Exception as e:
        logger.error(f"Anreicherungs-Fehler: {e}")
        click.echo(f"Fehler bei der Anreicherung: {e}", err=True)
        sys.exit(1)


@click.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--dry-run', is_flag=True,
              help='Nur anzeigen was getan würde, ohne Änderungen')
@click.option('--interactive', '-i', is_flag=True,
              help='Interaktiver Modus für Konflikte')
@click.option('--update-tags', is_flag=True,
              help='Tags mit gefundenen Metadaten aktualisieren')
@click.option('--fetch-youtube', is_flag=True,
              help='YouTube-Videos und Statistiken abrufen')
@click.pass_context
def enrich_single(ctx, file_path: str, dry_run: bool, interactive: bool, 
                 update_tags: bool, fetch_youtube: bool):
    """Reichert eine einzelne MP3-Datei mit Metadaten an."""
    
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    try:
        # API-Handler initialisieren
        metadata_resolver = MetadataResolver(config)
        youtube_handler = MultiPlatformVideoHandler(config)
        tag_manager = TagManager(config)
        conflict_resolver = ConflictResolver(config)
        
        # API-Status prüfen
        api_status = metadata_resolver.get_api_status()
        enabled_apis = [api for api, status in api_status.items() if status]
        
        if not enabled_apis:
            click.echo("⚠ Keine APIs aktiviert. Verwenden Sie 'mp3tagger setup-apis' zur Konfiguration.", err=True)
            sys.exit(1)
        
        click.echo(f"Verarbeite: {file_path}")
        click.echo(f"Aktive APIs: {', '.join(enabled_apis)}")
        
        if dry_run:
            click.echo("\n🔍 DRY-RUN Modus - Keine Änderungen werden vorgenommen!")
        
        # Async-Verarbeitung
        async def process_single_file():
            # Aktuelle Tags laden
            current_tags = tag_manager.read_tags(file_path)
            
            click.echo("\nAktuelle Tags:")
            for tag_id, value in current_tags.items():
                if tag_id in ['TIT2', 'TPE1', 'TALB', 'TDRC', 'TCON']:
                    tag_names = {
                        'TIT2': 'Titel',
                        'TPE1': 'Künstler',
                        'TALB': 'Album', 
                        'TDRC': 'Jahr',
                        'TCON': 'Genre'
                    }
                    click.echo(f"  {tag_names.get(tag_id, tag_id)}: {value[0] if value else 'Leer'}")
            
            # Basis-Informationen für Suche
            search_artist = current_tags.get('TPE1', [''])[0] if 'TPE1' in current_tags else ''
            search_title = current_tags.get('TIT2', [''])[0] if 'TIT2' in current_tags else ''
            
            if not search_artist and not search_title:
                # Versuche aus Dateiname zu extrahieren
                from ..utils.string_matching import extract_artist_title_from_filename
                extracted = extract_artist_title_from_filename(Path(file_path).name)
                if extracted:
                    search_artist, search_title = extracted
                    click.echo(f"\nExtrahiert aus Dateiname: {search_artist} - {search_title}")
            
            if not search_artist or not search_title:
                click.echo("⚠ Unzureichende Informationen für Metadaten-Suche")
                return
            
            click.echo(f"\nSuche nach: {search_artist} - {search_title}")
            
            # Metadaten sammeln
            enrichment_data = {}
            
            # Standard-APIs durchsuchen
            if 'musicbrainz' in enabled_apis:
                click.echo("Suche in MusicBrainz...")
                mb_results = await metadata_resolver.search_musicbrainz(search_artist, search_title)
                if mb_results:
                    enrichment_data['musicbrainz'] = mb_results[0]
                    click.echo(f"  ✓ {len(mb_results)} Ergebnis(se) gefunden")
                else:
                    click.echo("  ⚠ Keine Ergebnisse")
            
            if 'spotify' in enabled_apis:
                click.echo("Suche in Spotify...")
                spotify_results = await metadata_resolver.search_spotify(search_artist, search_title)
                if spotify_results:
                    enrichment_data['spotify'] = spotify_results[0]
                    click.echo("  ✓ Ergebnis gefunden")
                else:
                    click.echo("  ⚠ Keine Ergebnisse")
            
            if 'lastfm' in enabled_apis:
                click.echo("Suche in Last.fm...")
                lastfm_results = await metadata_resolver.search_lastfm(search_artist, search_title)
                if lastfm_results:
                    enrichment_data['lastfm'] = lastfm_results
                    click.echo("  ✓ Track-Info gefunden")
                else:
                    click.echo("  ⚠ Keine Ergebnisse")
            
            # YouTube-Videos abrufen (falls gewünscht)
            if fetch_youtube and 'youtube' in enabled_apis:
                click.echo("Suche YouTube-Videos...")
                try:
                    youtube_results = await youtube_handler.search_videos(f"{search_artist} {search_title}")
                    if youtube_results:
                        # Bestes Video (höchste Klickzahl)
                        best_video = max(youtube_results, key=lambda v: v.get('view_count', 0))
                        enrichment_data['youtube'] = best_video
                        click.echo(f"  ✓ {len(youtube_results)} Video(s) gefunden")
                        click.echo(f"  Bestes Video: {best_video.get('title', 'Unbekannt')} ({best_video.get('view_count', 0):,} Views)")
                    else:
                        click.echo("  ⚠ Keine Videos gefunden")
                except Exception as e:
                    click.echo(f"  ✗ YouTube-Fehler: {e}")
            
            # Anreicherung durchführen, wenn Daten gefunden
            if enrichment_data:
                click.echo("\nVorgeschlagene Metadaten:")
                
                # Konflikte auflösen
                resolved_tags = conflict_resolver.resolve_metadata_conflicts(
                    current_tags, enrichment_data
                )
                
                # Änderungen anzeigen
                changes = []
                for tag_id, new_value in resolved_tags.items():
                    if tag_id not in current_tags or str(current_tags[tag_id][0]) != str(new_value):
                        old_value = str(current_tags[tag_id][0]) if tag_id in current_tags else 'Leer'
                        changes.append((tag_id, old_value, new_value))
                        
                        tag_names = {
                            'TIT2': 'Titel',
                            'TPE1': 'Künstler',
                            'TALB': 'Album', 
                            'TDRC': 'Jahr',
                            'TCON': 'Genre',
                            'TRCK': 'Track-Nr.'
                        }
                        tag_name = tag_names.get(tag_id, tag_id)
                        click.echo(f"  {tag_name}: {old_value} → {new_value}")
                
                if changes:
                    if interactive and not dry_run:
                        if not click.confirm("\nÄnderungen übernehmen?"):
                            click.echo("Anreicherung abgebrochen.")
                            return
                    
                    # Tags schreiben (falls nicht dry-run)
                    if not dry_run and update_tags:
                        tag_manager.write_tags(file_path, resolved_tags)
                        click.echo("\n✓ Datei erfolgreich angereichert!")
                    elif dry_run:
                        click.echo("\n🔍 DRY-RUN: Änderungen würden übernommen werden.")
                    else:
                        click.echo("\n💡 Verwenden Sie --update-tags um die Änderungen zu übernehmen.")
                else:
                    click.echo("\nKeine neuen Metadaten gefunden.")
            else:
                click.echo("\nKeine Metadaten in den verfügbaren APIs gefunden.")
        
        # Async-Verarbeitung starten
        asyncio.run(process_single_file())
        
    except Exception as e:
        logger.error(f"Anreicherungs-Fehler: {e}")
        click.echo(f"Fehler bei der Anreicherung: {e}", err=True)
        sys.exit(1)
