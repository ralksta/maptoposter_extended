import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.colors as mcolors
import numpy as np
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import json
import os
from datetime import datetime
import argparse

THEMES_DIR = "themes"
FONTS_DIR = "fonts"
POSTERS_DIR = "posters"

def load_fonts():
    """
    Load Roboto fonts from the fonts directory.
    Returns dict with font paths for different weights.
    """
    fonts = {
        'bold': os.path.join(FONTS_DIR, 'Roboto-Bold.ttf'),
        'regular': os.path.join(FONTS_DIR, 'Roboto-Regular.ttf'),
        'light': os.path.join(FONTS_DIR, 'Roboto-Light.ttf')
    }
    
    # Verify fonts exist
    for weight, path in fonts.items():
        if not os.path.exists(path):
            print(f"⚠ Font not found: {path}")
            return None
    
    return fonts

FONTS = load_fonts()

def generate_output_filename(city, theme_name):
    """
    Generate unique output filename with city, theme, and datetime.
    """
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(' ', '_')
    filename = f"{city_slug}_{theme_name}_{timestamp}.png"
    return os.path.join(POSTERS_DIR, filename)

def get_available_themes():
    """
    Scans the themes directory and returns a list of available theme names.
    """
    if not os.path.exists(THEMES_DIR):
        os.makedirs(THEMES_DIR)
        return []
    
    themes = []
    for file in sorted(os.listdir(THEMES_DIR)):
        if file.endswith('.json'):
            theme_name = file[:-5]  # Remove .json extension
            themes.append(theme_name)
    return themes

def load_theme(theme_name="feature_based"):
    """
    Load theme from JSON file in themes directory.
    """
    theme_file = os.path.join(THEMES_DIR, f"{theme_name}.json")
    
    if not os.path.exists(theme_file):
        print(f"⚠ Theme file '{theme_file}' not found. Using default feature_based theme.")
        # Fallback to embedded default theme
        return {
            "name": "Feature-Based Shading",
            "bg": "#FFFFFF",
            "text": "#000000",
            "gradient_color": "#FFFFFF",
            "water": "#C0C0C0",
            "parks": "#F0F0F0",
            "road_motorway": "#0A0A0A",
            "road_primary": "#1A1A1A",
            "road_secondary": "#2A2A2A",
            "road_tertiary": "#3A3A3A",
            "road_residential": "#4A4A4A",
            "road_default": "#3A3A3A"
        }
    
    with open(theme_file, 'r') as f:
        theme = json.load(f)
        print(f"✓ Loaded theme: {theme.get('name', theme_name)}")
        if 'description' in theme:
            print(f"  {theme['description']}")
        return theme

# Load theme (can be changed via command line or input)
THEME = None  # Will be loaded later

def create_gradient_fade(ax, color, location='bottom', zorder=10):
    """
    Creates a fade effect at the top or bottom of the map.
    """
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))
    
    rgb = mcolors.to_rgb(color)
    my_colors = np.zeros((256, 4))
    my_colors[:, 0] = rgb[0]
    my_colors[:, 1] = rgb[1]
    my_colors[:, 2] = rgb[2]
    
    if location == 'bottom':
        my_colors[:, 3] = np.linspace(1, 0, 256)
        extent_y_start = 0
        extent_y_end = 0.25
    else:
        my_colors[:, 3] = np.linspace(0, 1, 256)
        extent_y_start = 0.75
        extent_y_end = 1.0

    custom_cmap = mcolors.ListedColormap(my_colors)
    
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_range = ylim[1] - ylim[0]
    
    y_bottom = ylim[0] + y_range * extent_y_start
    y_top = ylim[0] + y_range * extent_y_end
    
    ax.imshow(gradient, extent=[xlim[0], xlim[1], y_bottom, y_top], 
              aspect='auto', cmap=custom_cmap, zorder=zorder, origin='lower')

def get_edge_colors_by_type(G):
    """
    Assigns colors to edges based on road type hierarchy.
    Returns a list of colors corresponding to each edge in the graph.
    """
    edge_colors = []
    
    for u, v, data in G.edges(data=True):
        # Get the highway type (can be a list or string)
        highway = data.get('highway', 'unclassified')
        
        # Handle list of highway types (take the first one)
        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'
        
        # Assign color based on road type
        if highway in ['motorway', 'motorway_link']:
            color = THEME['road_motorway']
        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']:
            color = THEME['road_primary']
        elif highway in ['secondary', 'secondary_link']:
            color = THEME['road_secondary']
        elif highway in ['tertiary', 'tertiary_link']:
            color = THEME['road_tertiary']
        elif highway in ['residential', 'living_street', 'unclassified']:
            color = THEME['road_residential']
        else:
            color = THEME['road_default']
        
        edge_colors.append(color)
    
    return edge_colors

def get_edge_widths_by_type(G):
    """
    Assigns line widths to edges based on road type.
    Major roads get thicker lines.
    """
    edge_widths = []
    
    for u, v, data in G.edges(data=True):
        highway = data.get('highway', 'unclassified')
        
        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'
        
        # Assign width based on road importance
        if highway in ['motorway', 'motorway_link']:
            width = 1.2
        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']:
            width = 1.0
        elif highway in ['secondary', 'secondary_link']:
            width = 0.8
        elif highway in ['tertiary', 'tertiary_link']:
            width = 0.6
        else:
            width = 0.4
        
        edge_widths.append(width)
    
    return edge_widths

def get_coordinates(city, country):
    """
    Fetches coordinates for a given city and country using geopy.
    Returns a list of Location objects or None if no results found.
    Includes rate limiting to be respectful to the geocoding service.
    """
    print("Looking up coordinates...")
    geolocator = Nominatim(user_agent="city_map_poster")
    
    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)
    
    try:
        locations = geolocator.geocode(f"{city}, {country}", exactly_one=False, timeout=10, addressdetails=True)
        return locations
    except Exception as e:
        raise RuntimeError(f"API Error during geocoding: {e}")

def search_location(query):
    """
    Searches coordinates and address details for a given query (address, landmark, coordinates).
    Returns a list of Location objects or None if no results found.
    """
    print(f"Searching for '{query}'...")
    geolocator = Nominatim(user_agent="city_map_poster")
    
    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)
    
    try:
        locations = geolocator.geocode(query, exactly_one=False, timeout=10, addressdetails=True)
        return locations
    except Exception as e:
        raise RuntimeError(f"API Error during geocoding: {e}")

def get_city_from_address(location):
    """
    Intelligently extracts the best city/town/village/municipality name from Nominatim addressdetails.
    """
    if not location or not hasattr(location, 'raw'):
        return ""
    address = location.raw.get('address', {})
    if not address:
        return ""
    
    # Order of preference for determining the "city/town" name on a poster
    for key in ['city', 'town', 'village', 'municipality', 'suburb', 'hamlet', 'county', 'province', 'state', 'region']:
        if key in address:
            return address[key]
    return ""

def get_country_from_address(location):
    """
    Extracts the country name from Nominatim addressdetails.
    """
    if not location or not hasattr(location, 'raw'):
        return ""
    address = location.raw.get('address', {})
    return address.get('country', "")


def create_poster(city, country, point, dist, output_file, focus_point=None):
    print(f"\nGenerating map for {city}, {country}...")
    
    # Progress bar for data fetching
    with tqdm(total=3, desc="Fetching map data", unit="step", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
        # 1. Fetch Street Network
        pbar.set_description("Downloading street network")
        G = ox.graph_from_point(point, dist=dist, dist_type='bbox', network_type='all')
        pbar.update(1)
        time.sleep(0.5)  # Rate limit between requests
        
        # 2. Fetch Water Features
        pbar.set_description("Downloading water features")
        try:
            water_tags = {
                'natural': ['water', 'bay', 'strait'],
                'waterway': ['riverbank', 'dock', 'canal'],
                'place': ['sea', 'ocean']
            }
            water = ox.features_from_point(point, tags=water_tags, dist=dist)
            if water is not None and not water.empty:
                water = water[water.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        except:
            water = None
        pbar.update(1)
        time.sleep(0.3)
        
        # 3. Fetch Parks
        pbar.set_description("Downloading parks/green spaces")
        try:
            parks = ox.features_from_point(point, tags={'leisure': 'park', 'landuse': 'grass'}, dist=dist)
            if parks is not None and not parks.empty:
                parks = parks[parks.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        except:
            parks = None
        pbar.update(1)
    
    print("✓ All data downloaded successfully!")
    
    # 2. Setup Plot
    print("Rendering map...")
    fig, ax = plt.subplots(figsize=(12, 16), facecolor=THEME['bg'])
    ax.set_facecolor(THEME['bg'])
    ax.set_position([0, 0, 1, 1])
    
    # 3. Plot Layers
    # Layer 1: Polygons
    if water is not None and not water.empty:
        water.plot(ax=ax, facecolor=THEME['water'], edgecolor='none', zorder=1)
    if parks is not None and not parks.empty:
        parks.plot(ax=ax, facecolor=THEME['parks'], edgecolor='none', zorder=2)
    
    # Layer 2: Roads with hierarchy coloring
    print("Applying road hierarchy colors...")
    edge_colors = get_edge_colors_by_type(G)
    edge_widths = get_edge_widths_by_type(G)
    
    ox.plot_graph(
        G, ax=ax, bgcolor=THEME['bg'],
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=edge_widths,
        show=False, close=False
    )
    
    # Set explicit axis limits to ensure the center coordinates are perfectly in the middle of the poster
    import math
    lat, lon = point
    # 1 degree of latitude is ~111,111 meters
    delta_lat = dist / 111111.0
    # 1 degree of longitude depends on latitude: ~111,111 * cos(latitude) meters
    delta_lon = dist / (111111.0 * math.cos(math.radians(lat)))
    
    ax.set_xlim(lon - delta_lon, lon + delta_lon)
    ax.set_ylim(lat - delta_lat, lat + delta_lat)
    
    # Layer 2.5: Fokus-Punkt (falls gesetzt)
    if focus_point is not None:
        print("Platziere Fokus-Punkt auf der Karte...")
        focus_color = THEME.get('focus_color', '#E63946')
        ax.scatter(focus_point[1], focus_point[0], color=focus_color, s=350, zorder=9, edgecolor='white', linewidth=2.5)
    
    # Layer 3: Gradients (Top and Bottom)
    create_gradient_fade(ax, THEME['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, THEME['gradient_color'], location='top', zorder=10)
    
    # 4. Typography using Roboto font
    if FONTS:
        font_main = FontProperties(fname=FONTS['bold'], size=60)
        font_top = FontProperties(fname=FONTS['bold'], size=40)
        font_sub = FontProperties(fname=FONTS['light'], size=22)
        font_coords = FontProperties(fname=FONTS['regular'], size=14)
    else:
        # Fallback to system fonts
        font_main = FontProperties(family='monospace', weight='bold', size=60)
        font_top = FontProperties(family='monospace', weight='bold', size=40)
        font_sub = FontProperties(family='monospace', weight='normal', size=22)
        font_coords = FontProperties(family='monospace', size=14)
    
    spaced_city = "  ".join(list(city.upper()))

    # --- BOTTOM TEXT ---
    ax.text(0.5, 0.14, spaced_city, transform=ax.transAxes,
            color=THEME['text'], ha='center', fontproperties=font_main, zorder=11)
    
    ax.text(0.5, 0.10, country.upper(), transform=ax.transAxes,
            color=THEME['text'], ha='center', fontproperties=font_sub, zorder=11)
    
    lat, lon = point
    coords = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
    if lon < 0:
        coords = coords.replace("E", "W")
    
    ax.text(0.5, 0.07, coords, transform=ax.transAxes,
            color=THEME['text'], alpha=0.7, ha='center', fontproperties=font_coords, zorder=11)
    
    ax.plot([0.4, 0.6], [0.125, 0.125], transform=ax.transAxes, 
            color=THEME['text'], linewidth=1, zorder=11)

    # --- ATTRIBUTION (bottom right) ---
    if FONTS:
        font_attr = FontProperties(fname=FONTS['light'], size=8)
    else:
        font_attr = FontProperties(family='monospace', size=8)
    
    ax.text(0.98, 0.02, "© OpenStreetMap contributors", transform=ax.transAxes,
            color=THEME['text'], alpha=0.5, ha='right', va='bottom', 
            fontproperties=font_attr, zorder=11)

    # 5. Save
    print(f"Saving to {output_file}...")
    plt.savefig(output_file, dpi=300, facecolor=THEME['bg'])
    plt.close()
    print(f"✓ Done! Poster saved as {output_file}")

def print_examples():
    """Print usage examples."""
    print("""
City Map Poster Generator
=========================

Usage:
  python create_map_poster.py --city <city> --country <country> [options]

Examples:
  # Iconic grid patterns
  python create_map_poster.py -c "New York" -C "USA" -t noir -d 12000           # Manhattan grid
  python create_map_poster.py -c "Barcelona" -C "Spain" -t warm_beige -d 8000   # Eixample district grid
  
  # Waterfront & canals
  python create_map_poster.py -c "Venice" -C "Italy" -t blueprint -d 4000       # Canal network
  python create_map_poster.py -c "Amsterdam" -C "Netherlands" -t ocean -d 6000  # Concentric canals
  python create_map_poster.py -c "Dubai" -C "UAE" -t midnight_blue -d 15000     # Palm & coastline
  
  # Radial patterns
  python create_map_poster.py -c "Paris" -C "France" -t pastel_dream -d 10000   # Haussmann boulevards
  python create_map_poster.py -c "Moscow" -C "Russia" -t noir -d 12000          # Ring roads
  
  # Organic old cities
  python create_map_poster.py -c "Tokyo" -C "Japan" -t japanese_ink -d 15000    # Dense organic streets
  python create_map_poster.py -c "Marrakech" -C "Morocco" -t terracotta -d 5000 # Medina maze
  python create_map_poster.py -c "Rome" -C "Italy" -t warm_beige -d 8000        # Ancient street layout
  
  # Coastal cities
  python create_map_poster.py -c "San Francisco" -C "USA" -t sunset -d 10000    # Peninsula grid
  python create_map_poster.py -c "Sydney" -C "Australia" -t ocean -d 12000      # Harbor city
  python create_map_poster.py -c "Mumbai" -C "India" -t contrast_zones -d 18000 # Coastal peninsula
  
  # River cities
  python create_map_poster.py -c "London" -C "UK" -t noir -d 15000              # Thames curves
  python create_map_poster.py -c "Budapest" -C "Hungary" -t copper_patina -d 8000  # Danube split
  
  # List themes
  python create_map_poster.py --list-themes

Options:
  --city, -c        City name (required)
  --country, -C     Country name (required)
  --theme, -t       Theme name (default: feature_based)
  --distance, -d    Map radius in meters (default: 29000)
  --list-themes     List all available themes

Distance guide:
  4000-6000m   Small/dense cities (Venice, Amsterdam old center)
  8000-12000m  Medium cities, focused downtown (Paris, Barcelona)
  15000-20000m Large metros, full city view (Tokyo, Mumbai)

Available themes can be found in the 'themes/' directory.
Generated posters are saved to 'posters/' directory.
""")

def list_themes():
    """List all available themes with descriptions."""
    available_themes = get_available_themes()
    if not available_themes:
        print("No themes found in 'themes/' directory.")
        return
    
    print("\nAvailable Themes:")
    print("-" * 60)
    for theme_name in available_themes:
        theme_path = os.path.join(THEMES_DIR, f"{theme_name}.json")
        try:
            with open(theme_path, 'r') as f:
                theme_data = json.load(f)
                display_name = theme_data.get('name', theme_name)
                description = theme_data.get('description', '')
        except:
            display_name = theme_name
            description = ''
        print(f"  {theme_name}")
        print(f"    {display_name}")
        if description:
            print(f"    {description}")
        print()

def run_interactive_wizard():
    """
    Runs an interactive CLI wizard to gather parameters and generate a poster.
    """
    print("\n" + "=" * 60)
    print("⚓️  Moin Moin! Willkommen beim City Map Poster Generator Wizard!  ⚓️")
    print("=" * 60)
    print("Lass uns zusammen ein fettes Map-Poster basteln. Trag einfach die Infos ein.\n")
    
    coords = None
    actual_focus_coords = None
    city = ""
    country = ""
    selected_loc = None
    
    # 1. Ort/Fokuspunkt direkt abfragen & geokodieren
    while True:
        query = input("👉 Welchen Ort, welche Sehenswürdigkeit oder Adresse willst du zeigen? (z.B. 'Tokyo', 'Elbphilharmonie Hamburg'): ").strip()
        if not query:
            print("⚠ Ohne Ort läuft hier gar nix, Diggi! Trag bitte einen Namen ein.")
            continue
            
        try:
            locations = search_location(query)
            if not locations:
                print(f"\n⚠ Fehler: Konnte '{query}' nicht finden! Bitte überprüfe die Eingabe.\n")
                continue
                
            if len(locations) == 1:
                selected_loc = locations[0]
                coords = (selected_loc.latitude, selected_loc.longitude)
                resolved_address = selected_loc.address
                print(f"✓ Eindeutig gefunden: {resolved_address}")
                print(f"✓ Koordinaten: {coords[0]}, {coords[1]}\n")
                break
            else:
                # Multiple matches!
                print(f"\n🔎 Es wurden {len(locations)} passende Orte gefunden. Welchen meinst du?")
                top_locations = locations[:5]
                for idx, loc in enumerate(top_locations, 1):
                    print(f"  [{idx}] {loc.address}")
                print("  [0] Keiner davon (Suche verfeinern)")
                
                while True:
                    choice = input(f"Wähle eine Option [1-{len(top_locations)}] oder 0 (Standard: 1): ").strip()
                    if not choice:
                        choice_idx = 1
                    else:
                        try:
                            choice_idx = int(choice)
                        except ValueError:
                            print("⚠ Bitte gib eine Zahl ein, Diggi!")
                            continue
                            
                    if choice_idx == 0:
                        print("\nAlles klar, lass uns die Suche verfeinern.\n")
                        break  # Breaks inner selection loop, goes back to query input
                    elif 1 <= choice_idx <= len(top_locations):
                        selected_loc = top_locations[choice_idx - 1]
                        coords = (selected_loc.latitude, selected_loc.longitude)
                        resolved_address = selected_loc.address
                        print(f"✓ Ausgewählt: {resolved_address}")
                        print(f"✓ Koordinaten: {coords[0]}, {coords[1]}\n")
                        break
                        
                if choice_idx != 0:
                    break  # Break outer lookup loop
                    
        except Exception as e:
            print(f"\n⚠ Fehler bei der Ortssuche: {e}. Bitte versuche es noch einmal.\n")

    # 2. Fokus-Marker abfragen
    print("👉 Möchtest du an diesem Ort einen roten Fokuspunkt-Marker einzeichnen?")
    print("  [1] Nein, nackte Karte zentriert auf diesen Ort (Standard - ideal für Stadtkarten)")
    print("  [2] Ja, roten Fokuspunkt-Marker auf den Koordinaten platzieren")
    
    while True:
        choice = input("Wähle eine Option [1-2] (Standard: 1): ").strip()
        if not choice or choice == '1':
            actual_focus_coords = None
            print("✓ Karte wird zentriert, nackt ohne roten Marker gezeichnet.\n")
            break
        if choice == '2':
            actual_focus_coords = coords
            print("✓ Roter Fokuspunkt-Marker wird auf den Koordinaten eingezeichnet!\n")
            break
        print("⚠ Ungültige Auswahl. Bitte wähle 1 oder 2.")

    # 3. Beschriftung (Titel & Untertitel) mit intelligenten Vorschlägen abfragen
    detected_city = get_city_from_address(selected_loc)
    detected_country = get_country_from_address(selected_loc)
    
    print("👉 Lass uns jetzt die Beschriftung (Titel & Untertitel) für dein Poster festlegen.")
    
    while True:
        city_prompt = f"👉 Haupttitel für das Poster (Standard: {detected_city}): " if detected_city else "👉 Haupttitel für das Poster (z.B. Hamburg): "
        city_input = input(city_prompt).strip()
        if not city_input:
            city = detected_city
        else:
            city = city_input
        if city:
            break
        print("⚠ Ein Haupttitel wird benötigt, Diggi!")
        
    country_prompt = f"👉 Untertitel für das Poster (Standard: {detected_country}): " if detected_country else "👉 Untertitel für das Poster (z.B. Germany): "
    country_input = input(country_prompt).strip()
    if not country_input:
        country = detected_country
    else:
        country = country_input

    # 4. Theme
    available_themes = get_available_themes()
    print("\n👉 Welches Farbschema (Theme) hättest du gerne?")
    if available_themes:
        for idx, theme_name in enumerate(available_themes, 1):
            theme_path = os.path.join(THEMES_DIR, f"{theme_name}.json")
            display_name = theme_name
            try:
                with open(theme_path, 'r') as f:
                    theme_data = json.load(f)
                    display_name = theme_data.get('name', theme_name)
            except:
                pass
            print(f"  [{idx}] {theme_name} ({display_name})")
        
        default_theme_idx = 1
        if "feature_based" in available_themes:
            default_theme_idx = available_themes.index("feature_based") + 1
        elif "noir" in available_themes:
            default_theme_idx = available_themes.index("noir") + 1
            
        default_theme = available_themes[default_theme_idx - 1]
        
        while True:
            choice = input(f"Wähle eine Nummer [1-{len(available_themes)}] (Standard: {default_theme_idx} -> {default_theme}): ").strip()
            if not choice:
                theme = default_theme
                break
            try:
                choice_idx = int(choice)
                if 1 <= choice_idx <= len(available_themes):
                    theme = available_themes[choice_idx - 1]
                    break
            except ValueError:
                pass
            
            # Allow typing the theme name directly
            if choice in available_themes:
                theme = choice
                break
                
            print(f"⚠ Ungültige Auswahl. Bitte wähle eine Zahl zwischen 1 und {len(available_themes)} oder gib den Namen direkt ein.")
    else:
        print("  (Keine Themes im Ordner gefunden. Benutze Standard 'feature_based')")
        theme = "feature_based"

    # 5. Distance
    print("\n👉 Welchen Bildausschnitt (Radius in Metern) möchtest du zeigen?")
    print("  [1] Fokus auf die Innenstadt / Enger Ausschnitt (ca. 5.000m)")
    print("  [2] Fokus auf die Stadt / Mittlerer Ausschnitt (ca. 10.000m) -- Empfohlen!")
    print("  [3] Die ganze Metropole / Großer Ausschnitt (ca. 20.000m)")
    print("  [4] Custom / Selber in Metern eingeben")
    
    while True:
        dist_choice = input("Wähle eine Option [1-4] (Standard: 2 -> 10000m): ").strip()
        if not dist_choice:
            distance = 10000
            break
        if dist_choice == '1':
            distance = 5000
            break
        elif dist_choice == '2':
            distance = 10000
            break
        elif dist_choice == '3':
            distance = 20000
            break
        elif dist_choice == '4':
            while True:
                custom_dist = input("Gib den Radius in Metern ein (z.B. 12000): ").strip()
                try:
                    distance = int(custom_dist)
                    if distance > 0:
                        break
                    print("⚠ Der Radius muss größer als 0 sein.")
                except ValueError:
                    print("⚠ Bitte gib eine gültige Zahl ein.")
            break
        else:
            print("⚠ Ungültige Auswahl. Bitte wähle eine Option von 1 bis 4.")
            
    print("\n" + "=" * 50)
    print("Alles klar, Diggi! Hier ist dein Fahrplan:")
    print(f"  📍 Haupttitel: {city}")
    print(f"  📍 Untertitel: {country}")
    print(f"  🎨 Farbschema: {theme}")
    print(f"  📐 Radius:     {distance} Meter")
    if actual_focus_coords is None:
        print("  🔴 Fokus-Punkt: Keiner (nackte Karte zentriert)")
    else:
        print(f"  🔴 Fokus-Punkt: {actual_focus_coords[0]:.4f}, {actual_focus_coords[1]:.4f} (Mit Marker und zentriert)")
    print("=" * 50 + "\n")
    
    confirm = input("Sollen wir das Poster so generieren? [Y/n]: ").strip().lower()
    if confirm in ['', 'y', 'yes', 'ja']:
        # Load theme
        global THEME
        THEME = load_theme(theme)
        
        try:
            output_file = generate_output_filename(city, theme)
            create_poster(city, country, coords, distance, output_file, focus_point=actual_focus_coords)
            
            print("\n" + "=" * 50)
            print("✓ Poster-Generierung erfolgreich abgeschlossen!")
            print(f"Dein Kunstwerk liegt bereit unter: {output_file}")
            print("=" * 50)
            
        except Exception as e:
            print(f"\n✗ Fehler bei der Generierung: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Generierung abgebrochen. Tschüss, Diggi!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate beautiful map posters for any city",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_map_poster.py --city "New York" --country "USA"
  python create_map_poster.py --city Tokyo --country Japan --theme midnight_blue
  python create_map_poster.py --city Paris --country France --theme noir --distance 15000
  python create_map_poster.py --list-themes
  python create_map_poster.py --wizard
        """
    )
    
    parser.add_argument('--city', '-c', type=str, help='City name')
    parser.add_argument('--country', '-C', type=str, help='Country name')
    parser.add_argument('--theme', '-t', type=str, default='feature_based', help='Theme name (default: feature_based)')
    parser.add_argument('--distance', '-d', type=int, default=29000, help='Map radius in meters (default: 29000)')
    parser.add_argument('--focus', '-f', type=str, help='Focus point coordinates (latitude,longitude) to plot a red marker')
    parser.add_argument('--center-on-focus', '-cf', action='store_true', help='Center map directly on the focus coordinates instead of the city center')
    parser.add_argument('--list-themes', action='store_true', help='List all available themes')
    parser.add_argument('--wizard', '-w', action='store_true', help='Start interactive wizard')
    parser.add_argument('--select-first', '-y', action='store_true', help='Force using the first match if city name is ambiguous')
    
    args = parser.parse_args()
    
    # If no arguments provided or --wizard flag is used, run the wizard
    if len(os.sys.argv) == 1 or args.wizard:
        run_interactive_wizard()
        os.sys.exit(0)
    
    # List themes if requested
    if args.list_themes:
        list_themes()
        os.sys.exit(0)
    
    # Validate required arguments
    if not args.city or not args.country:
        print("Error: --city and --country are required for CLI mode.\n")
        print("💡 Tipp: Starte das Skript einfach ohne Argumente oder mit -w, um den interaktiven Wizard zu starten!\n")
        print_examples()
        os.sys.exit(1)
    
    # Validate theme exists
    available_themes = get_available_themes()
    if args.theme not in available_themes:
        print(f"Error: Theme '{args.theme}' not found.")
        print(f"Available themes: {', '.join(available_themes)}")
        os.sys.exit(1)
    
    print("=" * 50)
    print("City Map Poster Generator")
    print("=" * 50)
    
    # Load theme
    THEME = load_theme(args.theme)
    
    # Parse focus point if provided in CLI
    focus_coords = None
    if args.focus:
        try:
            lat_str, lon_str = args.focus.split(',')
            focus_coords = (float(lat_str.strip()), float(lon_str.strip()))
            print(f"✓ Fokus-Punkt Koordinaten geladen: {focus_coords}")
        except Exception as e:
            print(f"Error: Ungültiges Format für --focus. Muss 'latitude,longitude' sein (z.B. '53.5511,9.9937').")
            os.sys.exit(1)
            
    # Validate --center-on-focus has --focus
    if args.center_on_focus and not focus_coords:
        print("Error: --center-on-focus / -cf benötigt einen Fokuspunkt via --focus / -f!")
        os.sys.exit(1)
            
    # Get coordinates and generate poster
    try:
        locations = get_coordinates(args.city, args.country)
        if not locations:
            print(f"Error: Konnte keine Koordinaten für '{args.city}, {args.country}' finden! Bitte überprüfe die Schreibweise.")
            os.sys.exit(1)
            
        if len(locations) == 1:
            coords = (locations[0].latitude, locations[0].longitude)
            print(f"✓ Ort eindeutig gefunden: {locations[0].address}")
        else:
            # Ambiguity!
            if args.select_first:
                coords = (locations[0].latitude, locations[0].longitude)
                print(f"\033[93m⚠ Warnung: Mehrere Treffer für '{args.city}, {args.country}' gefunden!\033[0m")
                print(f"\033[93m  Wir verwenden den ersten Treffer: {locations[0].address}\033[0m")
            else:
                print(f"\n✗ Error: Der Ort '{args.city}, {args.country}' ist nicht eindeutig! Es wurden {len(locations)} Übereinstimmungen gefunden:")
                top_locations = locations[:5]
                for idx, loc in enumerate(top_locations, 1):
                    print(f"  [{idx}] {loc.address}")
                print("\n💡 Tipp: Nutze den interaktiven Wizard (ohne Parameter oder mit -w) oder übergib '-y' / '--select-first', um den ersten Treffer zu erzwingen.")
                os.sys.exit(1)
                
        output_file = generate_output_filename(args.city, args.theme)
        
        # Determine center coords
        if args.center_on_focus:
            center_coords = focus_coords
            print(f"✓ Kartenausschnitt wird auf den Fokus-Punkt zentriert: {center_coords}")
        else:
            center_coords = coords
            
        create_poster(args.city, args.country, center_coords, args.distance, output_file, focus_point=focus_coords)
        
        print("\n" + "=" * 50)
        print("✓ Poster generation complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        os.sys.exit(1)
