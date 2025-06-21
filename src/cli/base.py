"""
CLI Base Module - Setup und Hauptgruppe
"""

import click
import logging
import sys
from pathlib import Path
from typing import Optional

# Lokale Imports
from ..config_manager import get_config, ConfigManager


def setup_cli_logging(verbose: bool = False):
    """Konfiguriert das Logging für die Kommandozeile."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Einfacher Formatter für CLI mit führendem Leerzeichen für bessere Progressbar-Kompatibilität
    formatter = logging.Formatter(' %(levelname)s: %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Root Logger konfigurieren
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # CLI Handler hinzufügen (zusätzlich zu Config-Handlers)
    logger.addHandler(console_handler)
    
    # Störende Third-Party-Logs unterdrücken
    # MusicBrainz XML-Parser-Warnungen nur bei Debug-Level anzeigen
    logging.getLogger('musicbrainzngs').setLevel(logging.WARNING if not verbose else logging.DEBUG)
    
    # Google API Cache-Warnungen unterdrücken
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
    
    # Weitere potentiell störende Logs
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


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
