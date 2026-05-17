#!/bin/bash
# ⚓️ Startup script for the Map Poster Generator
# Ahoy! Just run it and the vessel will set sail!

# Get directory of this script to run it from anywhere
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "⚓️ Ahoy, Mate! Booting up, loading libraries... We're about to set sail!"

CONFIG_ARG=""
if [ $# -eq 0 ] && [ -d "configs" ]; then
    # Count config files
    configs=(configs/*.json)
    if [ ${#configs[@]} -gt 0 ] && [ -e "${configs[0]}" ]; then
        echo ""
        echo "👉 Look alive, I found some configuration charts in the 'configs/' locker:"
        echo "  [0] Launch fresh new wizard (clean slate)"
        i=1
        for conf in "${configs[@]}"; do
            filename=$(basename "$conf")
            echo "  [$i] $filename"
            ((i++))
        done
        
        read -p "Choose a chart [0-$((i-1))] (Default: 0): " sel
        if [[ "$sel" =~ ^[1-9][0-9]*$ ]] && [ "$sel" -le "$((i-1))" ]; then
            idx=$((sel-1))
            selected_config="${configs[$idx]}"
            echo "✓ Steered to chart: $selected_config"
            CONFIG_ARG="--config $selected_config"
        else
            echo "✓ Setting sail with a clean slate (no chart)."
        fi
        echo ""
    fi
fi

# Activate virtual environment and start script
if [ -d ".venv" ]; then
    source .venv/bin/activate
    # -u flag for unbuffered output to print immediately in terminal
    python -u create_map_poster.py $CONFIG_ARG "$@"
else
    echo "⚠ No virtual environment (.venv) found, Mate! Trying to navigate using system Python..."
    python3 -u create_map_poster.py $CONFIG_ARG "$@"
fi
