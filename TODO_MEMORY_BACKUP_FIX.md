# 🚧 TODO: In-Memory Backup Korrektur

## 📋 **Aufgabe**
Korrektur der In-Memory-Backup-Implementierung in `src/backup_manager.py`

## 🎯 **Problem**
Die aktuelle Implementierung lädt alle Dateien gleichzeitig in den RAM und hat ein `max_memory_mb` Limit. Das ist konzeptionell falsch.

## ✅ **Lösung**
Implementierung einer echten "eine-Datei-zur-Zeit" Strategie:

### **Zu ändernde Methoden:**

1. **`_create_memory_backup()`**
   - ❌ Entfernen: Speicherlimit-Prüfung
   - ✅ Sicherstellen: Nur eine Datei zur Zeit
   - ✅ Hinzufügen: Cleanup alter Transaktionen

2. **`cleanup_transaction()`** 
   - ✅ Implementieren: RAM freigeben nach erfolgreichem Update

3. **`restore_from_backup()`**
   - ✅ Verbessern: Wiederherstellung aus RAM + Cleanup

### **TagManager Integration:**
4. **`tag_manager.py`**
   - ✅ Aufrufe zu `cleanup_transaction()` nach erfolgreichem Tag-Update
   - ✅ Aufrufe zu `restore_from_backup()` bei Fehlern

## 📝 **Dateien zu bearbeiten:**
- `src/backup_manager.py` - Haupt-Implementierung  
- `src/tag_manager.py` - Integration
- `config/default_config.yaml` - Dokumentation Update

## 🧪 **Tests:**
- Memory-Backup für 1 Datei ✅
- Memory-Backup für 1000 Dateien ✅  
- Fehlerbehandlung + Restore ✅
- RAM-Verbrauch-Monitoring ✅

## 🚀 **Priorität:** Hoch
Die korrekte Implementierung macht In-Memory-Backup zur **besten Strategie** für alle Anwendungsfälle.

---
**Status:** 📋 Geplant  
**Erstellt:** 2025-06-21  
**Assignee:** Developer
