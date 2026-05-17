#!/bin/bash
# ⚓️ Start-Skript für den Map Poster Generator
# Diggi, einfach ausführen und der Kutter läuft!

# Pfad zum Verzeichnis des Skripts ermitteln, damit es von überall gestartet werden kann
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "⚓️ Moin! Bootvorgang läuft, Bibliotheken werden geladen... Gleich geht's los!"

CONFIG_ARG=""
if [ $# -eq 0 ] && [ -d "configs" ]; then
    # Zähle Config-Dateien
    configs=(configs/*.json)
    if [ ${#configs[@]} -gt 0 ] && [ -e "${configs[0]}" ]; then
        echo ""
        echo "👉 Ey, ich hab da ein paar Configs im 'configs/' Ordner gefunden:"
        echo "  [0] Keine nehmen (Wizard komplett neu starten)"
        i=1
        for conf in "${configs[@]}"; do
            filename=$(basename "$conf")
            echo "  [$i] $filename"
            ((i++))
        done
        
        read -p "Wähle eine Config [0-$((i-1))] (Standard: 0): " sel
        if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [ "$sel" -le "$((i-1))" ]; then
            idx=$((sel-1))
            selected_config="${configs[$idx]}"
            echo "✓ Schnapp mir die Config: $selected_config"
            CONFIG_ARG="--config $selected_config"
        else
            echo "✓ Starte nackig ohne Config."
        fi
        echo ""
    fi
fi

# Virtuelles Environment aktivieren und Skript starten
if [ -d ".venv" ]; then
    source .venv/bin/activate
    # -u flag für unbuffered output, damit prints sofort im Terminal landen!
    python -u create_map_poster.py $CONFIG_ARG "$@"
else
    echo "⚠ Keine virtuelle Umgebung (.venv) gefunden, Diggi! Versuche es mit System-Python..."
    python3 -u create_map_poster.py $CONFIG_ARG "$@"
fi
