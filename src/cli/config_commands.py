"""
CLI Config Commands - Konfiguration und API-Setup
"""

import click
import logging
import sys
import asyncio
from pathlib import Path

from ..metadata_resolver import MetadataResolver
from ..youtube_handler import YouTubeHandler, MultiPlatformVideoHandler


@click.command()
@click.pass_context  
def config_info(ctx):
    """Zeigt die aktuelle Konfiguration an."""
    
    config = ctx.obj['config']
    
    click.echo("="*50)
    click.echo("KONFIGURATIONSINFORMATIONEN")
    click.echo("="*50)
    
    # Konfigurationsdateien
    click.echo(f"Standard-Konfiguration: {config.default_config_path}")
    click.echo(f"Benutzer-Konfiguration: {config.user_config_path}")
    click.echo(f"Benutzer-Config existiert: {'Ja' if config.user_config_path.exists() else 'Nein'}")
    
    click.echo("\n" + "="*50)
    click.echo("API-KONFIGURATION")
    click.echo("="*50)
    
    # API-Konfiguration anzeigen (ohne Keys!)
    apis = config.get('apis', {})
    for api_name, api_config in apis.items():
        enabled = api_config.get('enabled', False)
        has_key = bool(api_config.get('api_key', '').strip())
        status = "✓ Aktiv" if enabled and has_key else "✗ Inaktiv"
        
        click.echo(f"{api_name.upper()}: {status}")
        if enabled and not has_key:
            click.echo(f"  ⚠ API-Key fehlt!")
    
    click.echo("\n" + "="*50)
    click.echo("TAG-EINSTELLUNGEN")
    click.echo("="*50)
    
    # Tag-Einstellungen
    tag_settings = config.get('tag_settings', {})
    conflict_resolution = tag_settings.get('conflict_resolution', 'ask')
    click.echo(f"Konfliktauflösung: {conflict_resolution}")
      # Custom Tags
    custom_tags = config.get('custom_tags', {})
    if custom_tags:
        click.echo(f"\nCustom Tags ({len(custom_tags)}):")
        for tag_name, tag_config in custom_tags.items():
            if isinstance(tag_config, dict):
                enabled = tag_config.get('enabled', False)
                status = "✓" if enabled else "✗"
                click.echo(f"  {status} {tag_name}")
            else:
                click.echo(f"  ? {tag_name} (invalid config)")
    
    # Geschützte Tags
    protected_tags = tag_settings.get('protected_tags', [])
    click.echo(f"\nGeschützte Tags ({len(protected_tags)}): {', '.join(protected_tags)}")


@click.command()
@click.pass_context  
def create_config(ctx):
    """Erstellt eine Benutzer-Konfigurationsvorlage."""
    
    config = ctx.obj['config']
    
    try:
        config.create_user_config_template()
        click.echo("✓ Benutzer-Konfigurationsvorlage erstellt")
        click.echo(f"Pfad: {config.user_config_path}")
        click.echo("\nBitte fügen Sie Ihre API-Schlüssel in die Datei ein.")
        
    except Exception as e:
        click.echo(f"Fehler beim Erstellen der Konfiguration: {e}", err=True)
        sys.exit(1)


@click.command()
@click.pass_context
def test_apis(ctx):
    """Testet die Verbindung zu den konfigurierten APIs."""
    
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    click.echo("="*50)
    click.echo("API-VERBINDUNGSTEST")
    click.echo("="*50)
    
    async def run_api_tests():
        # MetadataResolver testen
        resolver = MetadataResolver(config)
        
        # Test-Suche
        test_artist = "2Pac"
        test_title = "California Love"
        
        click.echo(f"Teste mit: {test_artist} - {test_title}")
        click.echo()
        
        # MusicBrainz Test
        click.echo("MusicBrainz API:")
        try:
            mb_results = await resolver.search_musicbrainz(test_artist, test_title)
            if mb_results:
                click.echo(f"  ✓ {len(mb_results)} Ergebnisse gefunden")
            else:
                click.echo("  ⚠ Keine Ergebnisse")
        except Exception as e:
            click.echo(f"  ✗ Fehler: {e}")
        
        # Spotify Test
        click.echo("Spotify API:")
        try:
            spotify_results = await resolver.search_spotify(test_artist, test_title)
            if spotify_results:
                click.echo(f"  ✓ {len(spotify_results)} Ergebnisse gefunden")
            else:
                click.echo("  ⚠ Keine Ergebnisse")
        except Exception as e:
            click.echo(f"  ✗ Fehler: {e}")
        
        # Last.fm Test
        click.echo("Last.fm API:")
        try:
            lastfm_results = await resolver.search_lastfm(test_artist, test_title)
            if lastfm_results:
                click.echo(f"  ✓ Track-Info gefunden")
            else:
                click.echo("  ⚠ Keine Ergebnisse")
        except Exception as e:
            click.echo(f"  ✗ Fehler: {e}")
        
        # YouTube Test
        click.echo("YouTube API:")
        try:
            youtube_handler = YouTubeHandler(config)
            youtube_results = await youtube_handler.search_videos(f"{test_artist} {test_title}")
            if youtube_results:
                click.echo(f"  ✓ {len(youtube_results)} Videos gefunden")
            else:
                click.echo("  ⚠ Keine Videos gefunden")
        except Exception as e:
            click.echo(f"  ✗ Fehler: {e}")
    
    try:
        asyncio.run(run_api_tests())
        click.echo("\n✓ API-Test abgeschlossen")
    except Exception as e:
        click.echo(f"\nFehler beim API-Test: {e}", err=True)


@click.command()
@click.pass_context
def setup_apis(ctx):
    """Interaktives Setup für API-Schlüssel."""
    
    config = ctx.obj['config']
    
    click.echo("="*50)
    click.echo("API-SETUP")
    click.echo("="*50)
    click.echo("Dieses Tool hilft Ihnen beim Einrichten der API-Schlüssel.")
    click.echo()
    
    # Sicherstellen, dass user_config existiert
    if not config.user_config_path.exists():
        click.echo("Erstelle Benutzer-Konfiguration...")
        config.create_user_config_template()
    
    apis_to_setup = {
        'spotify': {
            'name': 'Spotify',
            'url': 'https://developer.spotify.com/dashboard/applications',
            'description': 'Benötigt Client ID und Client Secret'
        },
        'youtube': {
            'name': 'YouTube Data API',
            'url': 'https://console.developers.google.com/apis/credentials',
            'description': 'Benötigt API Key'
        },
        'lastfm': {
            'name': 'Last.fm',
            'url': 'https://www.last.fm/api/account/create',
            'description': 'Benötigt API Key'
        }
    }
    
    for api_key, api_info in apis_to_setup.items():
        click.echo(f"\n{api_info['name']} Setup:")
        click.echo(f"Registrierung: {api_info['url']}")
        click.echo(f"Info: {api_info['description']}")
        
        if click.confirm(f"Möchten Sie {api_info['name']} jetzt konfigurieren?"):
            if api_key == 'spotify':
                client_id = click.prompt("Spotify Client ID", type=str)
                client_secret = click.prompt("Spotify Client Secret", type=str, hide_input=True)
                
                # In user_config speichern
                user_config = config.load_user_config()
                if 'apis' not in user_config:
                    user_config['apis'] = {}
                if 'spotify' not in user_config['apis']:
                    user_config['apis']['spotify'] = {}
                
                user_config['apis']['spotify']['client_id'] = client_id
                user_config['apis']['spotify']['client_secret'] = client_secret
                user_config['apis']['spotify']['enabled'] = True
                
                config.save_user_config(user_config)
                click.echo("✓ Spotify-Konfiguration gespeichert")
                
            else:
                api_key_value = click.prompt(f"{api_info['name']} API Key", type=str, hide_input=True)
                
                # In user_config speichern
                user_config = config.load_user_config()
                if 'apis' not in user_config:
                    user_config['apis'] = {}
                if api_key not in user_config['apis']:
                    user_config['apis'][api_key] = {}
                
                user_config['apis'][api_key]['api_key'] = api_key_value
                user_config['apis'][api_key]['enabled'] = True
                
                config.save_user_config(user_config)
                click.echo(f"✓ {api_info['name']}-Konfiguration gespeichert")
    
    click.echo("\n✓ API-Setup abgeschlossen!")
    click.echo("Verwenden Sie 'mp3tagger test-apis' um die Verbindung zu testen.")


@click.command()
@click.pass_context
def conflict_info(ctx):
    """Zeigt Informationen über Conflict Management und Batch-Rules."""
    
    config = ctx.obj['config']
    
    click.echo("="*60)
    click.echo("CONFLICT MANAGEMENT KONFIGURATION")
    click.echo("="*60)
      # Auto-Update Tags
    auto_update_tags = config.get('tag_settings.auto_update_tags', [])
    click.echo(f"\n🔄 Auto-Update Tags ({len(auto_update_tags)}):")
    click.echo("Diese Tags werden automatisch ohne Nachfrage überschrieben:")
    for tag in auto_update_tags:
        click.echo(f"  • {tag}")
    
    # Protected Tags
    protected_tags = config.get('tag_settings.protected_tags', [])
    click.echo(f"\n🛡️  Geschützte Tags ({len(protected_tags)}):")
    click.echo("Diese Tags werden NIEMALS überschrieben:")
    for tag in protected_tags:
        click.echo(f"  • {tag}")
    
    # Interactive Tags
    interactive_tags = config.get('tag_settings.interactive_tags', [])
    click.echo(f"\n👤 Interaktive Tags ({len(interactive_tags)}):")
    click.echo("Bei diesen Tags wird immer nachgefragt:")
    for tag in interactive_tags:
        click.echo(f"  • {tag}")
    
    # Batch Processing
    batch_config = config.get('tag_settings.conflict_resolution.batch_processing', {})
    click.echo(f"\n📦 Batch-Verarbeitung:")
    click.echo(f"  Aktiviert: {'✅' if batch_config.get('enabled', True) else '❌'}")
    click.echo(f"  Auto-Batch Schwelle: {batch_config.get('auto_batch_threshold', 5)} Konflikte")
    click.echo(f"  Entscheidungen merken: {'✅' if batch_config.get('remember_decisions', True) else '❌'}")
    click.echo(f"  Max. interaktive Nachfragen: {batch_config.get('max_interactive_prompts', 20)}")
    
    # Confidence Thresholds
    confidence_config = config.get('tag_settings.conflict_resolution.confidence_thresholds', {})
    click.echo(f"\n📊 Confidence-Schwellwerte:")
    click.echo(f"  Auto-Accept: ≥ {confidence_config.get('auto_accept', 0.95)*100:.0f}%")
    click.echo(f"  Empfehlung Accept: ≥ {confidence_config.get('recommend_accept', 0.80)*100:.0f}%")
    click.echo(f"  Warnung Low-Confidence: < {confidence_config.get('warn_low_confidence', 0.60)*100:.0f}%")
    
    # Gespeicherte Batch-Rules
    try:
        import json
        
        rules_file = Path("batch_rules.json")
        if rules_file.exists():
            with open(rules_file, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
                
            click.echo(f"\n🛠️  Gespeicherte Batch-Rules ({len(rules_data)}):")
            for rule_key, rule in rules_data.items():
                click.echo(f"  • {rule['pattern']} → {rule['action']} (verwendet: {rule['usage_count']}x)")
        else:
            click.echo(f"\n🛠️  Gespeicherte Batch-Rules: Keine gefunden")
    except Exception as e:
        click.echo(f"\n🛠️  Batch-Rules: Fehler beim Lesen ({e})")
    
    click.echo(f"\n💡 Tipps:")
    click.echo(f"  • Verwenden Sie --interactive für manuelle Kontrolle")
    click.echo(f"  • Erstellen Sie Batch-Rules für wiederholende Aufgaben")
    click.echo(f"  • Auto-Update Tags sind ideal für häufig wechselnde Daten")


@click.command()
@click.option('--clear-rules', is_flag=True, help='Löscht alle gespeicherten Batch-Rules')
@click.option('--clear-preferences', is_flag=True, help='Löscht alle Benutzer-Präferenzen')
@click.pass_context
def conflict_reset(ctx, clear_rules: bool, clear_preferences: bool):
    """Zurücksetzen von Conflict Management Einstellungen."""
    
    if not clear_rules and not clear_preferences:
        click.echo("⚠️  Keine Aktion gewählt. Verwenden Sie --clear-rules oder --clear-preferences")
        return
    
    if clear_rules:
        try:
            import json
            
            rules_file = Path("batch_rules.json")
            if rules_file.exists():
                rules_file.unlink()
                click.echo("✅ Batch-Rules gelöscht")
            else:
                click.echo("ℹ️  Keine Batch-Rules zum Löschen gefunden")
        except Exception as e:
            click.echo(f"❌ Fehler beim Löschen der Batch-Rules: {e}")
    
    if clear_preferences:
        try:
            prefs_file = Path("user_preferences.json")
            if prefs_file.exists():
                prefs_file.unlink()
                click.echo("✅ Benutzer-Präferenzen gelöscht")
            else:
                click.echo("ℹ️  Keine Benutzer-Präferenzen zum Löschen gefunden")
        except Exception as e:
            click.echo(f"❌ Fehler beim Löschen der Präferenzen: {e}")
