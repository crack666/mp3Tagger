@echo off
:: MP3 Tagger Installation Script für Windows
:: Alternative für Systeme ohne PowerShell-Unterstützung

echo MP3 Tagger Installation
echo ======================

:: Python-Version prüfen
echo.
echo Prüfe Python-Installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python ist nicht installiert oder nicht im PATH!
    echo Bitte installieren Sie Python von https://python.org
    pause
    exit /b 1
)

python --version
echo Python gefunden!

:: Pip upgraden
echo.
echo Upgrade pip...
python -m pip install --upgrade pip

:: Abhängigkeiten installieren
echo.
echo Installiere Abhängigkeiten...
pip install -r requirements.txt
if errorlevel 1 (
    echo FEHLER: Installation der Abhängigkeiten fehlgeschlagen!
    pause
    exit /b 1
)

:: Verzeichnisse erstellen
echo.
echo Erstelle benötigte Verzeichnisse...
if not exist logs mkdir logs
if not exist backups mkdir backups  
if not exist cache mkdir cache

:: Benutzer-Konfiguration erstellen
echo.
echo Konfiguration einrichten...
python main.py create-config

:: Test durchführen
echo.
echo Führe Test durch...
python main.py config-info

echo.
echo ==================================================
echo INSTALLATION ERFOLGREICH!
echo ==================================================
echo.
echo Nächste Schritte:
echo 1. Bearbeiten Sie config/user_config.yaml und fügen Sie Ihre API-Schlüssel hinzu
echo 2. Testen Sie das Tool mit: python main.py scan ./mp3s  
echo 3. Für Hilfe verwenden Sie: python main.py --help
echo.
echo Viel Erfolg mit MP3 Tagger! 🎵

pause
