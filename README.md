# ⚓️ Premium City Map Poster Generator

Generate breath-taking, gallery-grade minimalist map posters for any city or landmark in the world, complete with dynamic road hierarchies, overview insets, weather integration, and authentic texture overlays.

<p align="center">
  <img src="assets/hamburg_warm_beige.png" width="380" alt="Hamburg Portrait">
  <img src="assets/elbphilharmonie_noir.png" width="380" alt="Elbphilharmonie Portrait with Washi Texture">
</p>

---

## ✨ Features

- **🗺️ Complete Modular Engine**: Completely rewritten as a structured, clean, and highly maintainable Python package (`maptoposter/`).
- **🧙‍♂️ Interactive Setup Wizard**: An intelligent CLI wizard that guides you through geocoding, theme selection, size guides, custom layouts, and saves your setup for future automated runs.
- **🎨 20+ Curated Premium Themes**: A gorgeous selection of styles from the historic `warm_beige` and minimalist `noir` to the custom-tailored `waterkant` and `japanese_ink` styles.
- **📐 Dual Aspect Ratio Layouts**: 
  - `portrait`: Classic high-end wall poster format.
  - `landscape-plaque` / `gallery-plaque`: Gallery-style landscape plaque layout with a detailed metadata column on the right showing coordinates, weather, camera details, and region.
- **🗺️ Country Locator Insets**: Add an elegant mini country locator map in any corner (`top-left`, `top-right`, etc.) with a red marker pointing exactly to the city.
- **🌡️ Historical & Forecast Weather Integration**: Fetch and display precise temperature and weather descriptions (from Open-Meteo REST API) for the exact day and time your poster represents.
- **🔴 Focus Markers & centering**: Highlight landmarks, childhood homes, or special coordinates with a beautifully rendered red marker.
- **📝 Washi Paper Texture Overlay**: Apply an authentic, high-quality Japanese Washi paper texture overlay using advanced blending modes to give your poster a tactile, premium finish.

---

## 🚀 Installation

Ensure you have your environment set up. Run the automatic installer or do it manually:

```bash
# Manual installation
pip install -r requirements.txt
```

---

## ⚓️ Quick Start

Simply run the helper script to activate the virtual environment and start the generator:

```bash
# Start the interactive wizard directly (the easiest way!)
./run.sh
```

---

## 💻 CLI Usage

For power users, scripts, and automation, the generator exposes a full suite of CLI options:

```bash
python create_map_poster.py --city <city> --country <country> [options]
```

### Options

| Option | Short | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `--city` | `-c` | Name of the city | *Required* |
| `--country` | `-C` | Name of the country | *Required* |
| `--theme` | `-t` | Visual theme (21 pre-configured themes available) | `feature_based` |
| `--distance` | `-d` | Map radius in meters (determines zoom level) | `29000` |
| `--focus` | `-f` | Coordinates (`latitude,longitude`) to draw a red focal marker | `53.54129,9.9842` |
| `--center-on-focus` | `-cf` | Center map directly on focus coordinates instead of city center | `Flag` |
| `--show-inset` | `-i` | Enable country locator map inset | `Flag` |
| `--inset-position` | `-ip` | Position of country locator map | `top-left` \| `top-right` \| `bottom-left` \| `bottom-right` |
| `--date` | `-dt` | Date for weather and timestamp | `17.05.2026` or `2026-05-17` |
| `--time` | `-tm` | Time for weather and timestamp | `18:30` |
| `--no-weather` | | Show timestamp but disable fetching weather data | `Flag` |
| `--layout` | `-l` | Poster layout format | `portrait` \| `landscape-plaque` |
| `--no-card-title` | | Explicitly hide the title card directly on the map | `Flag` |
| `--show-card-title` | | Explicitly show the title card directly on the map | `Flag` |
| `--custom-note` | | Custom note / camera specifications for plaque layouts | `Maritime Archive Edition, 50mm Lens` |
| `--paper-texture` | | Apply the authentic Japanese Washi paper texture overlay | `Flag` |
| `--config` | | Path to a pre-defined JSON config file for headless wizard runs | `configs/my_setup.json` |
| `--select-first` | `-y` | Force using the first match if city name is ambiguous | `Flag` |
| `--list-themes` | | List all available themes with names and descriptions | `Flag` |
| `--wizard` | `-w` | Launch the interactive Setup Wizard | `Flag` |

---

### 🎨 Curated Themes

Choose from 20+ gorgeous, tailor-made color palettes:

- `feature_based`: Classic black & white with distinct road hierarchy.
- `gradient_roads`: Smooth, sleek gradient shading.
- `contrast_zones`: High contrast urban density.
- `noir`: Deep minimalist black background with clean white/gray roads.
- `midnight_blue`: Luxurious navy background with gold-colored roads.
- `blueprint`: Architectural blueprint aesthetic.
- `neon_cyberpunk`: High-voltage dark theme with electric pink and cyan.
- `warm_beige`: Cozy, vintage sepia map tones.
- `pastel_dream`: Muted, soft dreamy pastels.
- `japanese_ink`: Minimalist organic ink wash style.
- `forest`: Deep organic greens and sage tones.
- `ocean`: Vivid blues and teals for coastal cities.
- `terracotta`: Mediterranean brick-red warmth.
- `sunset`: Vibrant warm oranges and pinks.
- `autumn`: Seasonal burnt orange and rusty reds.
- `copper_patina`: Oxidized copper and patina green.
- `monochrome_blue`: Monochromatic ocean blue family.
- `waterkant`: True maritime Waterkant design, deep sea blue and bright whites.
- `ralf` / `ralf2`: Premium personal layouts with tailor-made contrasts.

---

### 🧙‍♂️ Wizard Automation

The interactive wizard allows you to build posters step-by-step and **save your configuration** to `configs/` as a JSON file. 

You can run the wizard in **completely headless, non-interactive mode** by passing the saved configuration:

```bash
python create_map_poster.py --config configs/my_saved_setup.json
```

**Example Configuration File (`configs/elbphilharmonie.json`):**
```jsonc
{
    // --- LOCATION OPTIONS ---
    "coord_input_mode": "1",            // Mode: "1" = Location search (Default), "2" = Manual GPS coordinates
    "query": "Elbphilharmonie Hamburg", // Search query for Nominatim geocoding (only active if coord_input_mode = "1")
    "location_choice": "1",             // Index of the selected match when multiple results are found (Default: "1")
    "manual_latitude": "53.5413",       // Latitude for manual GPS input (only active if coord_input_mode = "2")
    "manual_longitude": "9.9842",       // Longitude for manual GPS input (only active if coord_input_mode = "2")
    
    // --- FOCUS POINT / POSITIONING ---
    "focus_choice": "2",                // Red focal marker: "1" = None/clean map (Default), "2" = Red pin at coordinates
    
    // --- TEXT LABELS / TITLES ---
    "city": "Elbphilharmonie",          // Main title on the poster (Default: resolved city name)
    "country": "Germany",               // Subtitle / country on the poster (Default: resolved country name)
    
    // --- VISUAL MAP OPTIONS ---
    "theme_choice": "noir",             // Color scheme: Name of the theme (e.g. "noir", "waterkant") or index number
    "dist_choice": "1",                 // Zoom radius: "1" = 5km (tight), "2" = 10km (Default), "3" = 20km (wide), "4" = Custom manual input
    "custom_distance": "10000",         // Custom radius in meters (only active if dist_choice = "4")
    
    // --- LOCATOR MAP (INSET MAP) ---
    "inset_choice": "1",                // Inset locator map: "1" = Disabled (Default), "2" = Enabled (small country map with red pin)
    "inset_position": "1",              // Position of the inset map: "1" = Top-Left (Default), "2" = Top-Right, "3" = Bottom-Left, "4" = Bottom-Right
    
    // --- TIMESTAMP & HISTORICAL WEATHER ---
    "weather_time_choice": "1",         // Timestamp mode: "1" = Disabled (Default), "2" = Show timestamp & fetch weather
    "date_str": "17.05.2026",           // Date for weather & timestamp (Format: DD.MM.YYYY or YYYY-MM-DD)
    "time_str": "18:30",                // Optional time (Format: HH:MM, leave empty for midday)
    "show_weather_choice": "yes",       // Fetch weather details from Open-Meteo: "yes"/"y" = Yes (Default), "no"/"n" = No
    
    // --- LAYOUT & FORMATS ---
    "layout_choice": "1",               // Layout format: "1" = Classic Portrait (Default), "2" = Gallery Info Plaque Landscape (landscape-plaque)
    "title_choice": "1",                // Draw title directly on the map portion for plaque layout: "1" = Disabled (Default), "2" = Enabled
    "custom_note": "Maritime Edition",   // Custom text note / camera details for landscape plaque layout (optional)
    "use_paper_texture": "yes",         // Apply organic Japanese Washi paper texture overlay: "yes"/"y" = Yes, "no"/"n" = No (Default)
    "format": "1",                      // Output file format: "1" = PNG (Default), "2" = SVG (Vector), "3" = PDF (Print-ready)
    "font_family": "Montserrat",        // Custom Google Font name (e.g. "Montserrat"), leave empty for theme default
    "width": "12.0",                    // Custom width in inches (optional, max 20.0, leave empty for default layout aspect ratio)
    "height": "18.0",                   // Custom height in inches (optional, max 20.0, leave empty for default layout aspect ratio)

    // --- DIALOG AUTOMATION ---
    "confirm_generation": "yes",        // Skip confirmation prompt and start generation immediately: "yes"/"y" = Yes, "no"/"n" = No
    "save_config_name": "n"             // Save config file under specified filename: name (e.g. "hamburg") or "n" = No
}
```
```

---

## 🛠️ Project Structure

```
maptoposter_extended/
├── maptoposter/          # Core package modules
│   ├── __init__.py       # Package initialization
│   ├── cli.py            # CLI entry and arg parsing
│   ├── geocoding.py      # Nominatim & Geopy geographical lookups
│   ├── generator.py      # Matplotlib and PIL rendering engine
│   ├── theme.py          # Theme loader and Font managers
│   ├── weather.py        # Open-Meteo REST API & WMO parser
│   └── wizard.py         # Step-by-step interactive wizard dialog
├── themes/               # Curated JSON theme palettes
├── fonts/                # Custom TTF fonts (e.g. Roboto)
├── posters/              # Generated high-resolution output files
├── assets/               # Static assets (Washi texture overlay)
├── configs/              # User-saved wizard configurations
├── create_map_poster.py  # Thin orchestrator and entrypoint
├── run.sh                # Virtual env setup helper
└── README.md
```

---

## 💻 Hacker's Guide

This guide details internal mechanisms for developers extending the generator.

### Pipeline Architecture

```
                               ┌──────────────────┐
                               │ create_map_poster│
                               └──────────────────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │   maptoposter │
                                └───────────────┘
                                        │
                  ┌─────────────┬───────┴─────┬─────────────┐
                  ▼             ▼             ▼             ▼
             ┌──────────┐ ┌──────────┐  ┌───────────┐ ┌───────────┐
             │  cli.py  │ │wizard.py │  │theme.py   │ │generator.e│
             └──────────┘ └──────────┘  └───────────┘ └───────────┘
                                                            │
                                                      ┌─────┴─────┐
                                                      ▼           ▼
                                                ┌──────────┐┌───────────┐
                                                │geocoding.││weather.py │
                                                └──────────┘└───────────┘
```

### Z-Order & Rendering Layers

When rendering elements in `create_poster()`, the layer stacking order ensures premium styling without overlaps:

| Z-Order | Elements | Description |
| :--- | :--- | :--- |
| `11` | Text Labels | Spaced City title, country, coordinates, and attributions |
| `10` | Gradient Fades | Top and bottom custom ListedColormap alpha gradients |
| `9` | Focus Point | Red focal marker dot with a crisp white border |
| `3` | Roads | Plotted OSMnx networks colored based on highway hierarchy |
| `2` | Parks | Green spaces and leisure polygons |
| `1` | Water | Canals, rivers, oceans, and natural waterways |
| `0` | Background | Base canvas background color |

### Custom Theme Schema

Themes are simple, declarative JSON files. You can customize focus point sizing and colors inside the JSON:

```json
{
  "name": "Maritime Waterkant",
  "description": "True maritime deep sea blue and bright whites",
  "bg": "#0D1B2A",
  "text": "#E0E1DD",
  "gradient_color": "#0D1B2A",
  "water": "#1B263B",
  "parks": "#415A77",
  "road_motorway": "#FFFFFF",
  "road_primary": "#E0E1DD",
  "road_secondary": "#A5A5A5",
  "road_tertiary": "#7B8C9E",
  "road_residential": "#4F5D75",
  "road_default": "#3D4856",
  "focus_color": "#D62828",
  "focus_size": 400,
  "focus_edge_color": "white",
  "focus_edge_width": 2.5
}
```

---

## ⚖️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

⚓️ *Developed with passion for premium cartographic art.*
