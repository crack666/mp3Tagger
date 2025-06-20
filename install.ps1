# MP3 Tagger Installation Script für Windows
# Dieses Skript installiert alle Abhängigkeiten und richtet das Tool ein

Write-Host "MP3 Tagger Installation" -ForegroundColor Green
Write-Host "======================" -ForegroundColor Green

# Python-Version prüfen
Write-Host "`nPrüfe Python-Installation..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1
    Write-Host "Gefunden: $pythonVersion" -ForegroundColor Green
    
    # Python-Version extrahieren
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $majorVersion = [int]$matches[1]
        $minorVersion = [int]$matches[2]
        
        if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 8)) {
            Write-Host "FEHLER: Python 3.8 oder höher ist erforderlich!" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "FEHLER: Python ist nicht installiert oder nicht im PATH!" -ForegroundColor Red
    Write-Host "Bitte installieren Sie Python von https://python.org" -ForegroundColor Red
    exit 1
}

# Pip upgraden
Write-Host "`nUpgrade pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Virtual Environment erstellen (optional)
$createVenv = Read-Host "`nMöchten Sie ein Virtual Environment erstellen? (empfohlen) [J/n]"
if ($createVenv -eq "" -or $createVenv -eq "J" -or $createVenv -eq "j") {
    Write-Host "Erstelle Virtual Environment..." -ForegroundColor Yellow
    python -m venv venv
    
    Write-Host "Aktiviere Virtual Environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
    
    Write-Host "Virtual Environment aktiviert!" -ForegroundColor Green
}

# Abhängigkeiten installieren
Write-Host "`nInstalliere Abhängigkeiten..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "FEHLER: Installation der Abhängigkeiten fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

# Verzeichnisse erstellen
Write-Host "`nErstelle benötigte Verzeichnisse..." -ForegroundColor Yellow
$directories = @("logs", "backups", "cache")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "Erstellt: $dir" -ForegroundColor Green
    }
}

# Benutzer-Konfiguration erstellen
Write-Host "`nKonfiguration einrichten..." -ForegroundColor Yellow
python main.py create-config

# Test durchführen
Write-Host "`nFühre Test durch..." -ForegroundColor Yellow
python main.py config-info

Write-Host "`n" + "="*50 -ForegroundColor Green
Write-Host "INSTALLATION ERFOLGREICH!" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Green

Write-Host "`nNächste Schritte:" -ForegroundColor Yellow
Write-Host "1. Bearbeiten Sie config/user_config.yaml und fügen Sie Ihre API-Schlüssel hinzu"
Write-Host "2. Testen Sie das Tool mit: python main.py scan ./mp3s"
Write-Host "3. Für Hilfe verwenden Sie: python main.py --help"

if ($createVenv -eq "" -or $createVenv -eq "J" -or $createVenv -eq "j") {
    Write-Host "`nWICHTIG: Virtual Environment aktivieren mit:" -ForegroundColor Red
    Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Red
}

Write-Host "`nViel Erfolg mit MP3 Tagger! 🎵" -ForegroundColor Green
