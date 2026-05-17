#!/bin/bash
# ⚓️ Start-Skript für den Map Poster Generator
# Diggi, einfach ausführen und der Kutter läuft!

# Pfad zum Verzeichnis des Skripts ermitteln, damit es von überall gestartet werden kann
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "⚓️ Moin! Bootvorgang läuft, Bibliotheken werden geladen... Gleich geht's los!"

# Virtuelles Environment aktivieren und Skript starten
if [ -d ".venv" ]; then
    source .venv/bin/activate
    # -u flag für unbuffered output, damit prints sofort im Terminal landen!
    python -u create_map_poster.py "$@"
else
    echo "⚠ Keine virtuelle Umgebung (.venv) gefunden, Diggi! Versuche es mit System-Python..."
    python3 -u create_map_poster.py "$@"
fi
