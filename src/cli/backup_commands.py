"""
Backup Management CLI Commands für MP3 Tagger.
"""

import click
import json
from pathlib import Path
from tabulate import tabulate


@click.group()
def backup():
    """Backup-Management Kommandos."""
    pass


@backup.command('status')
@click.option('--format', 'output_format', 
              type=click.Choice(['table', 'json']), 
              default='table',
              help='Ausgabeformat')
def backup_status(output_format):
    """Zeigt Backup-Status und Statistiken an."""
    try:
        from ..tag_manager import TagManager
        from ..config_manager import get_config
        
        config = get_config()
        tag_manager = TagManager(config)
        stats = tag_manager.get_backup_stats()
        
        if output_format == 'json':
            click.echo(json.dumps(stats, indent=2, default=str))
        else:
            # Tabellen-Ausgabe
            click.echo(f"\n📊 Backup-Status")
            click.echo("=" * 50)
            
            basic_info = [
                ["Strategie", stats['strategy']],
                ["Backup-Verzeichnis", stats['backup_dir']],
                ["Aktive Transaktionen", stats['active_transactions']],
                ["RAM-Verbrauch", f"{stats['memory_usage_mb']:.2f} MB"]
            ]
            
            click.echo(tabulate(basic_info, headers=["Eigenschaft", "Wert"], tablefmt="grid"))
            
            # Backup-Counts
            if 'changelog_entries' in stats:
                click.echo(f"\n📝 Changelog-Einträge: {stats['changelog_entries']}")
            
            if 'selective_backups' in stats:
                click.echo(f"🎯 Selective Backups: {stats['selective_backups']}")
            
            if 'full_backups' in stats:
                click.echo(f"💾 Full Backups: {stats['full_backups']}")
            
            click.echo(f"\n📦 Gesamt Backups: {stats['total_backups']}")
            
    except Exception as e:
        click.echo(f"❌ Fehler: {e}", err=True)


@backup.command('cleanup')
@click.option('--dry-run', is_flag=True, 
              help='Zeigt nur an, was gelöscht würde')
@click.option('--force', is_flag=True,
              help='Überspringt Bestätigung')
def backup_cleanup(dry_run, force):
    """Entfernt alte Backups basierend auf Konfiguration."""
    try:
        from ..tag_manager import TagManager
        from ..config_manager import get_config
        
        config = get_config()
        max_age = config.get('backup.max_age_days', 30)
        
        if not force:
            click.echo(f"⚠️  Entferne Backups älter als {max_age} Tage")
            if not click.confirm("Fortfahren?"):
                click.echo("Abgebrochen.")
                return
        
        if dry_run:
            click.echo("🔍 Dry-Run Modus - keine Dateien werden gelöscht")
            # TODO: Implementiere Dry-Run Logik im BackupManager
            return
        
        tag_manager = TagManager(config)
        removed_count = tag_manager.cleanup_old_backups()
        
        if removed_count > 0:
            click.echo(f"✅ {removed_count} alte Backups entfernt")
        else:
            click.echo("ℹ️  Keine alten Backups gefunden")
            
    except Exception as e:
        click.echo(f"❌ Fehler: {e}", err=True)


@backup.command('restore')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--timestamp', 
              help='Spezifischer Backup-Zeitstempel (YYYY-MM-DD_HH-MM-SS)')
@click.option('--force', is_flag=True,
              help='Überspringt Bestätigung')
def backup_restore(file_path, timestamp, force):
    """Stellt eine Datei aus dem Backup wieder her."""
    try:
        from ..tag_manager import TagManager
        from ..config_manager import get_config
        
        file_path = Path(file_path)
        
        if not force:
            warning_msg = f"⚠️  Datei '{file_path}' wird aus Backup wiederhergestellt"
            if timestamp:
                warning_msg += f" (Zeitstempel: {timestamp})"
            click.echo(warning_msg)
            if not click.confirm("Fortfahren?"):
                click.echo("Abgebrochen.")
                return
        
        config = get_config()
        tag_manager = TagManager(config)
        
        success = tag_manager.restore_from_backup(file_path, timestamp)
        
        if success:
            click.echo(f"✅ Datei erfolgreich wiederhergestellt: {file_path}")
        else:
            click.echo(f"❌ Wiederherstellung fehlgeschlagen: {file_path}")
            
    except Exception as e:
        click.echo(f"❌ Fehler: {e}", err=True)


@backup.command('strategy')
@click.argument('new_strategy', 
                type=click.Choice(['changelog', 'in_memory', 'selective', 'full_copy', 'disabled']))
@click.option('--force', is_flag=True,
              help='Überspringt Bestätigung')
def backup_strategy(new_strategy, force):
    """Ändert die Backup-Strategie."""
    try:
        from ..config_manager import get_config, update_config
        
        config = get_config()
        current_strategy = config.get('backup.strategy', 'changelog')
        
        if current_strategy == new_strategy:
            click.echo(f"ℹ️  Backup-Strategie ist bereits '{new_strategy}'")
            return
        
        if not force:
            click.echo(f"🔄 Ändere Backup-Strategie: {current_strategy} → {new_strategy}")
            
            strategy_info = {
                'changelog': 'Leichtgewichtige JSON-basierte Änderungsprotokolle (empfohlen)',
                'in_memory': 'RAM-basierte Transaktions-Backups für kleine Bibliotheken',
                'selective': 'Nur kritische Tags als kompakte JSON-Backups',
                'full_copy': 'Vollständige Dateikopien (nur für kleine Bibliotheken)',
                'disabled': 'Keine Backups (nicht empfohlen)'
            }
            
            click.echo(f"Neue Strategie: {strategy_info.get(new_strategy, 'Unbekannt')}")
            
            if not click.confirm("Fortfahren?"):
                click.echo("Abgebrochen.")
                return
        
        # Update configuration
        success = update_config('backup.strategy', new_strategy)
        
        if success:
            click.echo(f"✅ Backup-Strategie geändert: {new_strategy}")
            click.echo("ℹ️  Neustart des Tools empfohlen für vollständige Aktivierung")
        else:
            click.echo("❌ Fehler beim Ändern der Konfiguration")
        
    except Exception as e:
        click.echo(f"❌ Fehler: {e}", err=True)
