"""
MP3 Tagger - Entry Point

Haupteinstiegspunkt für das MP3-Tagging-Tool.
Alle CLI-Kommandos sind in separate Module ausgelagert.
"""

from src.cli.base import cli
from src.cli.scan_commands import scan, info  
from src.cli.config_commands import config_info, create_config, test_apis, setup_apis, conflict_info, conflict_reset
from src.cli.backup_commands import backup
from src.cli.enrich_commands import enrich, enrich_single


def main():
    """Haupteinstiegspunkt für das MP3 Tagger CLI."""    # Registriere alle Kommandos    cli.add_command(scan)
    cli.add_command(info)
    cli.add_command(config_info)
    cli.add_command(create_config)
    cli.add_command(test_apis)
    cli.add_command(setup_apis)
    cli.add_command(conflict_info)
    cli.add_command(conflict_reset)
    cli.add_command(backup)
    cli.add_command(enrich)
    cli.add_command(enrich_single)
    
    # Starte CLI
    cli()


if __name__ == "__main__":
    main()
