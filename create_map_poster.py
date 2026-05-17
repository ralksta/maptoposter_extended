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
import requests

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

def generate_output_filename(city, theme_name, layout='portrait'):
    """
    Generate unique output filename with city, theme, and datetime.
    """
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(' ', '_')
    layout_suffix = f"_{layout}" if layout != 'portrait' else ""
    filename = f"{city_slug}_{theme_name}{layout_suffix}_{timestamp}.png"
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
        locations = geolocator.geocode(f"{city}, {country}", exactly_one=False, timeout=10, addressdetails=True, language='de')
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
        locations = geolocator.geocode(query, exactly_one=False, timeout=10, addressdetails=True, language='de')
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

def get_region_from_address(location):
    """
    Extracts the region, state, province or county name from Nominatim addressdetails.
    """
    if not location or not hasattr(location, 'raw'):
        return ""
    address = location.raw.get('address', {})
    for key in ['state', 'province', 'region', 'county', 'state_district']:
        if key in address:
            return address[key]
    return ""

# German month names for premium styling
GERMAN_MONTHS = {
    1: "JANUAR", 2: "FEBRUAR", 3: "MÄRZ", 4: "APRIL", 
    5: "MAI", 6: "JUNI", 7: "JULI", 8: "AUGUST", 
    9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DEZEMBER"
}

# WMO Weather Codes to Emojis and Descriptions
WMO_WEATHER_CODES = {
    0: "SONNIG",
    1: "FAST WOLKENLOS",
    2: "TEILWEISE BEWÖLKT",
    3: "BEWÖLKT",
    45: "NEBLIG",
    48: "NEBLIG RAGEND",
    51: "LEICHTER NIESELREGEN",
    53: "NIESELREGEN",
    55: "STARKER NIESELREGEN",
    56: "GEFRIERENDER NIESELREGEN",
    57: "STARKER GEFRIERENDER NIESELREGEN",
    61: "LEICHTER REGEN",
    63: "REGEN",
    65: "STARKER REGEN",
    66: "LEICHTER GEFRIERENDER REGEN",
    67: "STARKER GEFRIERENDER REGEN",
    71: "LEICHTER SCHNEEFALL",
    73: "SCHNEEFALL",
    75: "STARKER SCHNEEFALL",
    77: "SCHNEEGRISEL",
    80: "LEICHTER REGENSCHAUER",
    81: "REGENSCHAUER",
    82: "STARKER REGENSCHAUER",
    85: "LEICHTER SCHNEESCHAUER",
    86: "STARKER SCHNEESCHAUER",
    95: "GEWITTER",
    96: "GEWITTER MIT LEICHTEM HAGEL",
    99: "GEWITTER MIT HAGEL",
}

def parse_date_and_time(date_str, time_str=None):
    """
    Parses common German and international date/time formats robustly.
    Returns (parsed_date, parsed_time) or raises ValueError.
    """
    parsed_date = None
    parsed_time = None

    if date_str:
        date_str = date_str.strip()
        # Common formats to try
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if not parsed_date:
            raise ValueError(f"Ungültiges Datumsformat: '{date_str}'. Erlaubt sind z.B. 17.05.2026 oder 2026-05-17.")

    if time_str:
        time_str = time_str.strip().lower()
        if time_str.endswith("uhr"):
            time_str = time_str[:-3].strip()
        # Common formats to try
        for fmt in ("%H:%M", "%H"):
            try:
                parsed_time = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue
        if not parsed_time:
            raise ValueError(f"Ungültiges Uhrzeitformat: '{time_str}'. Erlaubt sind z.B. 18:30 oder 18.")

    return parsed_date, parsed_time

def fetch_weather_data(lat, lon, date_obj, time_obj=None):
    """
    Fetches historical weather (archive-api) or forecast (forecast-api)
    for the given coordinates and date. Returns (temp, weather_code).
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    today = datetime.now().date()
    
    # Select correct API based on target date vs today
    if date_obj.date() < today:
        api_url = "https://archive-api.open-meteo.com/v1/archive"
    else:
        api_url = "https://api.open-meteo.com/v1/forecast"
        
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,weather_code",
        "timezone": "auto"
    }
    
    print(f"Abfrage Wetterdaten über Open-Meteo ({'Archiv' if date_obj.date() < today else 'Vorhersage'})...")
    
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    hourly = data.get("hourly", {})
    if not hourly or "time" not in hourly:
        raise ValueError("Keine stündlichen Wetterdaten in der API-Antwort vorhanden.")
        
    target_hour = time_obj.hour if time_obj else 12
    times = hourly["time"]
    target_index = -1
    
    for idx, t_str in enumerate(times):
        try:
            dt = datetime.fromisoformat(t_str)
            if dt.hour == target_hour:
                target_index = idx
                break
        except Exception:
            continue
            
    if target_index == -1 and len(times) > target_hour:
        target_index = target_hour
        
    if target_index == -1 or target_index >= len(hourly["temperature_2m"]):
        raise ValueError(f"Konnte keinen passenden Datenpunkt für Stunde {target_hour} finden.")
        
    temp = hourly["temperature_2m"][target_index]
    code = hourly["weather_code"][target_index]
    
    return temp, code


def create_poster(city, country, point, dist, output_file, focus_point=None, show_inset=False, inset_position='top-left', date_str=None, time_str=None, show_weather=True, layout='portrait', no_card_title=None, region=None, custom_note=None):
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
    
    # Determine if we should hide the card title directly on the map
    if no_card_title is None:
        should_hide_card_title = (layout in ['landscape-plaque', 'gallery-plaque'])
    else:
        should_hide_card_title = no_card_title

    # 2. Setup Plot
    print("Rendering map...")
    if layout in ['landscape-plaque', 'gallery-plaque']:
        # DM Photo format 10x15cm perfectly matches a 15:10 aspect ratio
        fig_width = 15 if layout == 'gallery-plaque' else 16
        fig = plt.figure(figsize=(fig_width, 10), facecolor=THEME['bg'])
        # Map-Plot links (aspect ratio layout)
        ax = fig.add_axes([0.04, 0.04, 0.53, 0.92])
        ax.set_facecolor(THEME['bg'])
        # Info-Plot rechts
        ax_info = fig.add_axes([0.61, 0.04, 0.35, 0.92])
        ax_info.set_facecolor(THEME['bg'])
        ax_info.axis('off')
    else:
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
    scale = 3.5 if layout == 'gallery-plaque' else 1.0
    edge_widths = [w * scale for w in get_edge_widths_by_type(G)]
    
    ox.plot_graph(
        G, ax=ax, bgcolor=THEME['bg'],
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=edge_widths,
        show=False, close=False
    )
    
    # Ensure map borders are styled for plaque layout
    if layout in ['landscape-plaque', 'gallery-plaque']:
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(THEME['text'])
            spine.set_linewidth(1.5 * scale)
            spine.set_alpha(0.8)
    
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
        focus_size = THEME.get('focus_size', 350)
        focus_edge_color = THEME.get('focus_edge_color', 'white')
        focus_edge_width = THEME.get('focus_edge_width', 2.5)
        
        ax.scatter(focus_point[1], focus_point[0], 
                   color=focus_color, 
                   s=focus_size * (scale**2), 
                   zorder=9, 
                   edgecolor=focus_edge_color, 
                   linewidth=focus_edge_width * scale)
    
    # Layer 3: Gradients (Top and Bottom)
    create_gradient_fade(ax, THEME['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, THEME['gradient_color'], location='top', zorder=10)
    
    # Fetch historical/forecast weather data if date is provided
    weather_info_str = ""
    weather_val_str = ""
    datetime_val_str = ""
    if date_str:
        try:
            parsed_date, parsed_time = parse_date_and_time(date_str, time_str)
            
            # Format German premium date string (e.g. 17. MAI 2026)
            month_idx = parsed_date.month
            month_name = GERMAN_MONTHS.get(month_idx, parsed_date.strftime("%B").upper())
            formatted_date = f"{parsed_date.day}. {month_name} {parsed_date.year}"
            
            if parsed_time:
                formatted_time = parsed_time.strftime("%H:%M")
                datetime_str = f"{formatted_date} / {formatted_time} UHR"
            else:
                datetime_str = formatted_date
            
            datetime_val_str = datetime_str
                
            weather_str = ""
            if show_weather:
                try:
                    temp, code = fetch_weather_data(point[0], point[1], parsed_date, parsed_time)
                    desc = WMO_WEATHER_CODES.get(code, "WETTER")
                    weather_str = f"{desc}, {temp:.1f}°C"
                    weather_val_str = weather_str
                except Exception as we:
                    print(f"⚠ Warning: Wetterdaten konnten nicht geladen werden: {we}")
                    
            if weather_str:
                weather_info_str = f"{datetime_str}  •  {weather_str}"
            else:
                weather_info_str = datetime_str
                
        except Exception as e:
            print(f"⚠ Warning: Zeitstempel konnte nicht verarbeitet werden: {e}")
    
    # 4. Typography using Roboto font or dynamic system fonts/files from theme
    font_title_val = THEME.get('font_title')
    font_body_val = THEME.get('font_body')
    font_mono_val = THEME.get('font_mono')
    
    def get_font_prop(font_val, default_family='sans-serif', **kwargs):
        if not font_val:
            # Check if default fonts are available
            if FONTS:
                weight = kwargs.get('weight', 'normal')
                if weight == 'bold':
                    return FontProperties(fname=FONTS['bold'], size=kwargs.get('size'))
                elif weight == 'light':
                    return FontProperties(fname=FONTS['light'], size=kwargs.get('size'))
                else:
                    return FontProperties(fname=FONTS['regular'], size=kwargs.get('size'))
            return FontProperties(family=default_family, **kwargs)
            
        # Try to resolve as a local file
        resolved_path = None
        if os.path.exists(font_val):
            resolved_path = font_val
        elif os.path.exists(os.path.join(FONTS_DIR, font_val)):
            resolved_path = os.path.join(FONTS_DIR, font_val)
        elif not font_val.lower().endswith(('.ttf', '.otf')):
            for ext in ['.ttf', '.otf', '.TTF', '.OTF']:
                p = os.path.join(FONTS_DIR, font_val + ext)
                if os.path.exists(p):
                    resolved_path = p
                    break
                p_direct = font_val + ext
                if os.path.exists(p_direct):
                    resolved_path = p_direct
                    break
                    
        if resolved_path:
            return FontProperties(fname=resolved_path, size=kwargs.get('size'))
        else:
            return FontProperties(family=font_val, **kwargs)
            
    font_main = get_font_prop(font_title_val, 'sans-serif', weight='bold', size=int(60 * scale))
    font_top = get_font_prop(font_title_val, 'sans-serif', weight='bold', size=int(40 * scale))
    font_sub = get_font_prop(font_body_val, 'sans-serif', 
                            weight='light' if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else 'normal', 
                            size=int(22 * scale))
    font_coords = get_font_prop(font_mono_val, 'monospace', size=int(14 * scale))
    font_attr = get_font_prop(font_mono_val, 'monospace', size=int(8 * scale))
    
    # Info Panel Fonts
    font_info_title = get_font_prop(font_title_val, 'sans-serif', weight='bold', size=int(32 * scale))
    font_info_sub = get_font_prop(font_body_val, 'sans-serif', 
                                  weight='light' if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else 'normal', 
                                  size=int(20 * scale))
    font_info_label = get_font_prop(font_body_val, 'sans-serif', weight='normal', size=int(13 * scale))
    font_info_val = get_font_prop(font_title_val, 'sans-serif', weight='bold', size=int(18 * scale))
    font_info_val_reg = get_font_prop(font_body_val, 'sans-serif', weight='normal', size=int(18 * scale))
    
    # Render Bottom text on Map only if not hidden
    if not should_hide_card_title:
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
        
        if weather_info_str:
            ax.text(0.5, 0.04, weather_info_str, transform=ax.transAxes,
                    color=THEME['text'], alpha=0.7, ha='center', fontproperties=font_coords, zorder=11)
        
        ax.plot([0.4, 0.6], [0.125, 0.125], transform=ax.transAxes, 
                color=THEME['text'], linewidth=1, zorder=11)
        
        # --- ATTRIBUTION (bottom right) ---
        ax.text(0.98, 0.02, "© OpenStreetMap contributors", transform=ax.transAxes,
                color=THEME['text'], alpha=0.5, ha='right', va='bottom', 
                fontproperties=font_attr, zorder=11)

    # --- LANDSCAPE PLAQUE INFO PANEL ---
    if layout in ['landscape-plaque', 'gallery-plaque']:
        print("Rendering right information column...")
        
        # 1. Title section
        # Dynamic title font size based on length
        title_text = city.upper()
        title_len = len(title_text)
        if title_len > 25:
            title_size = int(20 * scale)
        elif title_len > 18:
            title_size = int(24 * scale)
        else:
            title_size = int(32 * scale)
            
        font_info_title.set_size(title_size)
        
        y_pos = 0.90
        
        # Draw City Name
        ax_info.text(0.0, y_pos, title_text, transform=ax_info.transAxes,
                     color=THEME['text'], ha='left', va='top', fontproperties=font_info_title, wrap=True)
        
        # Height adjustment for city title (if wrapped or long)
        y_pos -= 0.08
        if title_len > 18:
            y_pos -= 0.04
            
        # Draw Country Name
        ax_info.text(0.0, y_pos, country.upper(), transform=ax_info.transAxes,
                     color=THEME['text'], ha='left', va='top', fontproperties=font_info_sub)
        
        y_pos -= 0.05
        
        # Draw a beautiful horizontal separator line in theme text color
        ax_info.plot([0.0, 0.9], [y_pos, y_pos], transform=ax_info.transAxes,
                     color=THEME['text'], linewidth=1.5 * scale, alpha=0.8)
        
        y_pos -= 0.08
        
        # 2. Stacked labels
        # Stack 1: Region / Province
        if not region:
            try:
                geolocator = Nominatim(user_agent="city_map_poster_region")
                time.sleep(0.5)
                locs = geolocator.geocode(f"{city}, {country}", addressdetails=True, timeout=10, language='de')
                if locs:
                    region = get_region_from_address(locs)
            except Exception as e:
                print(f"⚠ Region konnte nicht geholt werden: {e}")
                
        if region:
            ax_info.text(0.0, y_pos, "REGION / PROVINZ", transform=ax_info.transAxes,
                         color=THEME['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, region.upper(), transform=ax_info.transAxes,
                         color=THEME['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 2: Zeitstempel / Date
        if datetime_val_str:
            ax_info.text(0.0, y_pos, "ZEITPUNKT", transform=ax_info.transAxes,
                         color=THEME['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, datetime_val_str.upper(), transform=ax_info.transAxes,
                         color=THEME['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 3: Klima & Wetter
        if weather_val_str:
            ax_info.text(0.0, y_pos, "KLIMA & WETTER", transform=ax_info.transAxes,
                         color=THEME['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, weather_val_str.upper(), transform=ax_info.transAxes,
                         color=THEME['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 4: Custom Note / Kamera
        if custom_note:
            ax_info.text(0.0, y_pos, "KAMERA", transform=ax_info.transAxes,
                         color=THEME['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            
            # Ohne wrap=True, um Darstellungsprobleme (z.B. "blassere" Schrift in manchen Backends) zu vermeiden
            ax_info.text(0.0, y_pos, custom_note.upper(), transform=ax_info.transAxes,
                         color=THEME['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075

        # Stack 5: Koordinaten / GPS
        lat, lon = point
        coords_val_str = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
        if lon < 0:
            coords_val_str = coords_val_str.replace("E", "W")
            
        ax_info.text(0.0, y_pos, "GPS-KOORDINATEN", transform=ax_info.transAxes,
                     color=THEME['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
        y_pos -= 0.035
        ax_info.text(0.0, y_pos, coords_val_str, transform=ax_info.transAxes,
                     color=THEME['text'], ha='left', va='top', fontproperties=font_info_val)
        y_pos -= 0.075
        
        # Lower attribution text
        ax_info.text(0.0, 0.01, "© OpenStreetMap contributors", transform=ax_info.transAxes,
                     color=THEME['text'], alpha=0.4, ha='left', va='bottom', fontproperties=font_attr)

    # Layer 4: Optionale Landeskarte (Inset-Map)
    if show_inset:
        print(f"Versuche Landeskarte (Inset) für {country} zu laden...")
        try:
            # 1. Geometrie des Landes laden
            gdf_country = ox.geocode_to_gdf(country)
            if gdf_country is not None and not gdf_country.empty:
                minx, miny, maxx, maxy = gdf_country.total_bounds
                data_w = maxx - minx
                data_h = maxy - miny
                aspect = data_h / data_w if data_w > 0 else 1.0

                # 2. Position des Insets bestimmen basierend auf inset_position und layout
                if layout in ['landscape-plaque', 'gallery-plaque']:
                    fig_w = 15 if layout == 'gallery-plaque' else 16
                    width = 0.11
                    height = (width * fig_w * aspect) / 10.0
                    
                    # The map area is [0.04, 0.04, 0.53, 0.92]
                    map_left, map_top = 0.04, 0.96
                    map_right, map_bottom = 0.57, 0.04
                    
                    # Gleichmäßiger Abstand zum Kartenrand (nicht zum Bildrand)
                    margin_x = 0.015 
                    margin_y = margin_x * (fig_w / 10.0)
                    
                    if inset_position == 'top-left':
                        left, bottom = map_left + margin_x, map_top - margin_y - height
                    elif inset_position == 'top-right':
                        left, bottom = map_right - margin_x - width, map_top - margin_y - height
                    elif inset_position == 'bottom-left':
                        left, bottom = map_left + margin_x, map_bottom + margin_y
                    elif inset_position == 'bottom-right':
                        left, bottom = map_right - margin_x - width, map_bottom + margin_y
                else:
                    width = 0.16
                    height = (width * 12 * aspect) / 16.0  # perfectly square for 12:16 figure
                    if inset_position == 'top-left':
                        left, bottom = 0.05, 0.95 - height
                    elif inset_position == 'top-right':
                        left, bottom = 0.95 - width, 0.95 - height
                    elif inset_position == 'bottom-left':
                        left, bottom = 0.05, 0.05
                    elif inset_position == 'bottom-right':
                        left, bottom = 0.95 - width, 0.05
                    else:
                        left, bottom = 0.05, 0.95 - height  # Fallback
                
                # 3. Neue Achse hinzufügen
                inset_ax = fig.add_axes([left, bottom, width, height], facecolor=THEME['water'])
                
                # 4. Land plotten
                # Umrissfarbe: THEME['text'], Füllung: THEME.get('parks') oder THEME['bg']
                land_color = THEME.get('parks', THEME['bg'])
                border_color = THEME['text']
                gdf_country.plot(ax=inset_ax, facecolor=land_color, edgecolor=border_color, linewidth=0.5)
                
                # Exakte Anpassung auf die Bounding-Box, um interne Ränder zu eliminieren
                inset_ax.set_xlim(minx, maxx)
                inset_ax.set_ylim(miny, maxy)
                inset_ax.set_axis_off()
                
                # 5. Fokuspunkt/Kartenzentrum als roten Punkt einzeichnen
                lat, lon = point
                focus_color = THEME.get('focus_color', '#B43B3B')
                inset_ax.scatter(lon, lat, color=focus_color, s=40 * (scale**2), zorder=5, edgecolor='white', linewidth=1 * scale)
                
                # 6. Achsen & Spines designen
                inset_ax.set_xticks([])
                inset_ax.set_yticks([])
                
                # Edler dünner Rahmen in Textfarbe
                for spine in inset_ax.spines.values():
                    spine.set_color(THEME['text'])
                    spine.set_linewidth(0.8 * scale)
                    spine.set_alpha(0.8)
                    
                print("✓ Landeskarte (Inset) erfolgreich hinzugefügt!")
        except Exception as e:
            print(f"⚠ Warning: Landeskarte für {country} konnte nicht gerendert werden: {e}")

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

def run_interactive_wizard(config_path=None):
    """
    Runs an interactive CLI wizard to gather parameters and generate a poster.
    Supports prepopulating and skipping questions via a config file.
    """
    print("\n" + "=" * 60)
    print("⚓️  Moin Moin! Willkommen beim City Map Poster Generator Wizard!  ⚓️")
    print("=" * 60)
    print("Lass uns zusammen ein fettes Map-Poster basteln. Trag einfach die Infos ein.\n")
    
    config = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✓ Config '{config_path}' geladen.")
        except Exception as e:
            print(f"⚠ Fehler beim Laden der Config: {e}")

    final_config = {}

    def wizard_input(prompt, key):
        if key in config:
            val = str(config[key])
            print(f"{prompt}{val}  (Aus Config)")
            del config[key]
            final_config[key] = val
            return val
        
        val = input(prompt).strip()
        final_config[key] = val
        return val

    coords = None
    actual_focus_coords = None
    city = ""
    country = ""
    selected_loc = None
    
    # 1. Ort/Fokuspunkt direkt abfragen & geokodieren
    while True:
        query = wizard_input("👉 Welchen Ort, welche Sehenswürdigkeit oder Adresse willst du zeigen? (z.B. 'Tokyo', 'Elbphilharmonie Hamburg'): ", "query")
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
                    choice = wizard_input(f"Wähle eine Option [1-{len(top_locations)}] oder 0 (Standard: 1): ", "location_choice")
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
        choice = wizard_input("Wähle eine Option [1-2] (Standard: 1): ", "focus_choice")
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
        city_input = wizard_input(city_prompt, "city")
        if not city_input:
            city = detected_city
        else:
            city = city_input
        if city:
            break
        print("⚠ Ein Haupttitel wird benötigt, Diggi!")
        
    country_prompt = f"👉 Untertitel für das Poster (Standard: {detected_country}): " if detected_country else "👉 Untertitel für das Poster (z.B. Germany): "
    country_input = wizard_input(country_prompt, "country")
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
            choice = wizard_input(f"Wähle eine Nummer [1-{len(available_themes)}] (Standard: {default_theme_idx} -> {default_theme}): ", "theme_choice")
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
        dist_choice = wizard_input("Wähle eine Option [1-4] (Standard: 2 -> 10000m): ", "dist_choice")
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
                custom_dist = wizard_input("Gib den Radius in Metern ein (z.B. 12000): ", "custom_distance")
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
            
    # 6. Landeskarte (Inset-Map) abfragen
    show_inset = False
    inset_position = 'top-left'
    
    print("\n👉 Möchtest du eine kleine Übersichtskarte des Landes (Inset-Map) in einer Ecke anzeigen?")
    print("  [1] Nein (Standard)")
    print("  [2] Ja, Übersichtskarte anzeigen")
    
    while True:
        choice = wizard_input("Wähle eine Option [1-2] (Standard: 1): ", "inset_choice")
        if not choice or choice == '1':
            show_inset = False
            print("✓ Keine Übersichtskarte auf dem Poster.\n")
            break
        if choice == '2':
            show_inset = True
            print("✓ Übersichtskarte wird auf dem Poster eingezeichnet!\n")
            
            print("👉 In welcher Ecke soll die Übersichtskarte platziert werden?")
            print("  [1] Oben Links (Standard)")
            print("  [2] Oben Rechts")
            print("  [3] Unten Links (Über dem Text)")
            print("  [4] Unten Rechts (Über dem Text)")
            
            while True:
                pos_choice = wizard_input("Wähle eine Option [1-4] (Standard: 1): ", "inset_position")
                if not pos_choice or pos_choice == '1':
                    inset_position = 'top-left'
                    break
                elif pos_choice == '2':
                    inset_position = 'top-right'
                    break
                elif pos_choice == '3':
                    inset_position = 'bottom-left'
                    break
                elif pos_choice == '4':
                    inset_position = 'bottom-right'
                    break
                else:
                    print("⚠ Ungültige Auswahl. Bitte wähle eine Option von 1 bis 4.")
            
            print(f"✓ Position für Übersichtskarte festgelegt auf: {inset_position}\n")
            break
        print("⚠ Ungültige Auswahl. Bitte wähle 1 oder 2.")

    # 7. Wetter & Zeitstempel abfragen
    date_str = None
    time_str = None
    show_weather = True

    print("\n👉 Möchtest du einen Zeitstempel und Wetterinfos auf dem Poster anzeigen?")
    print("  [1] Nein (Standard)")
    print("  [2] Ja, Datum/Uhrzeit eingeben und Wetterdaten laden")

    while True:
        choice = wizard_input("Wähle eine Option [1-2] (Standard: 1): ", "weather_time_choice")
        if not choice or choice == '1':
            date_str = None
            time_str = None
            show_weather = False
            print("✓ Kein Zeitstempel und keine Wetterdaten auf dem Poster.\n")
            break
        if choice == '2':
            # Ask for date
            while True:
                d_input = wizard_input("👉 Datum eingeben (z.B. '17.05.2026' oder '2026-05-17'): ", "date_str")
                if not d_input:
                    print("⚠ Ein Datum wird benötigt für den Zeitstempel, Diggi!")
                    continue
                try:
                    parse_date_and_time(d_input, None)
                    date_str = d_input
                    break
                except ValueError as ve:
                    print(f"⚠ {ve} Bitte versuche es noch einmal.")
            
            # Ask for time
            t_input = wizard_input("👉 Uhrzeit optional eingeben (z.B. '18:30', '18 Uhr' oder leer lassen für Mittagszeit): ", "time_str")
            if t_input:
                while True:
                    try:
                        parse_date_and_time(date_str, t_input)
                        time_str = t_input
                        break
                    except ValueError as ve:
                        print(f"⚠ {ve} Bitte versuche es noch einmal.")
                        t_input = wizard_input("👉 Uhrzeit optional eingeben: ", "time_str")
                        if not t_input:
                            break

            # Ask for weather
            weather_choice = wizard_input("👉 Wetterinfos (Temperatur & Bewölkung) laden und anzeigen? [Y/n] (Standard: Y): ", "show_weather_choice").lower()
            if weather_choice in ['', 'y', 'yes', 'ja']:
                show_weather = True
                print("✓ Wetterdaten werden von Open-Meteo geladen!")
            else:
                show_weather = False
                print("✓ Nur Zeitstempel wird angezeigt (ohne Wetter).")
            print()
            break
        print("⚠ Ungültige Auswahl. Bitte wähle 1 oder 2.")

    # 8. Layout-Format abfragen
    layout = 'portrait'
    no_card_title = None

    print("\n👉 Welches Layout-Format soll dein Poster haben?")
    print("  [1] Hochformat / Classic Portrait (Standard - ideal für die Wand)")
    print("  [2] Querformat / Galerie-Infoplakette (Schickes 16:10 Format mit Infotext rechts)")
    
    while True:
        choice = wizard_input("Wähle eine Option [1-2] (Standard: 1): ", "layout_choice")
        if not choice or choice == '1':
            layout = 'portrait'
            print("✓ Layout festgelegt auf: Classic Portrait (Hochformat)\n")
            break
        if choice == '2':
            layout = 'landscape-plaque'
            print("✓ Layout festgelegt auf: Galerie-Infoplakette (Querformat)\n")
            
            # Bei der Plakette nach dem Titel auf der Karte fragen
            print("👉 Möchtest du bei der Plakette zusätzlich einen Titel direkt auf der Karte einzeichnen?")
            print("  [1] Nein, Karte clean halten (Standard - empfohlen)")
            print("  [2] Ja, Titel auch auf der Karte anzeigen")
            while True:
                title_choice = wizard_input("Wähle eine Option [1-2] (Standard: 1): ", "title_choice")
                if not title_choice or title_choice == '1':
                    no_card_title = True
                    print("✓ Karte bleibt clean ohne Titel.\n")
                    break
                elif title_choice == '2':
                    no_card_title = False
                    print("✓ Titel wird auch auf der Karte gezeichnet.\n")
                    break
                else:
                    print("⚠ Bitte wähle 1 oder 2.")
            break
        print("⚠ Bitte wähle 1 oder 2.")

    # 9. Custom Note
    custom_note = None
    if layout in ['landscape-plaque', 'gallery-plaque']:
        print("\n👉 Möchtest du Kamera-Details (Freitext) hinzufügen? (Optional)")
        note_input = wizard_input("Gib deine Kamera-Details ein (leer lassen für keine Angabe): ", "custom_note")
        if note_input.strip():
            custom_note = note_input
            print("✓ Kamera-Details hinzugefügt.")

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
    if show_inset:
        print(f"  🗺 Landeskarte: Ja (Position: {inset_position})")
    else:
        print("  🗺 Landeskarte: Nein")
    if date_str:
        t_str = f" um {time_str}" if time_str else ""
        w_str = " (mit Wetter)" if show_weather else " (ohne Wetter)"
        print(f"  📅 Zeitstempel: {date_str}{t_str}{w_str}")
    else:
        print("  📅 Zeitstempel: Nein")
    print(f"  📐 Layout:     {'Classic Portrait (Hochformat)' if layout == 'portrait' else 'Galerie-Infoplakette (Querformat)'}")
    if layout == 'landscape-plaque':
        print(f"  📛 Kartentitel: {'Clean (Ausgeblendet)' if no_card_title else 'Anzeigen'}")
    if custom_note:
        print(f"  📷 Kamera:     {custom_note}")
    print("=" * 50 + "\n")
    
    confirm = wizard_input("Sollen wir das Poster so generieren? [Y/n]: ", "confirm_generation").lower()
    if confirm in ['', 'y', 'yes', 'ja']:
        # Load theme
        global THEME
        THEME = load_theme(theme)
        
        try:
            region = get_region_from_address(selected_loc)
            output_file = generate_output_filename(city, theme, layout=layout)
            create_poster(city, country, coords, distance, output_file, focus_point=actual_focus_coords, show_inset=show_inset, inset_position=inset_position, date_str=date_str, time_str=time_str, show_weather=show_weather, layout=layout, no_card_title=no_card_title, region=region, custom_note=custom_note)
            
            print("\n" + "=" * 50)
            print("✓ Poster-Generierung erfolgreich abgeschlossen!")
            print(f"Dein Kunstwerk liegt bereit unter: {output_file}")
            print("=" * 50)
            
            save_name = wizard_input("\n👉 Möchtest du diese Konfiguration speichern? [Name/n] (Standard: n): ", "save_config_name")
            if save_name and save_name.lower() != 'n':
                if not save_name.endswith('.json'):
                    save_name += '.json'
                
                # Make sure the configs directory exists
                os.makedirs("configs", exist_ok=True)
                save_path = os.path.join("configs", save_name)
                
                # Filter out the confirm and save_config_name keys
                cfg_to_save = {k: v for k, v in final_config.items() if k not in ['confirm_generation', 'save_config_name']}
                
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg_to_save, f, indent=4, ensure_ascii=False)
                print(f"✓ Konfiguration gespeichert als '{save_path}'")
            
            
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
    parser.add_argument('--show-inset', '-i', action='store_true', help='Show country locator/inset map in one of the corners')
    parser.add_argument('--inset-position', '-ip', type=str, default='top-left', choices=['top-left', 'top-right', 'bottom-left', 'bottom-right'], help='Position of the country inset map (default: top-left)')
    parser.add_argument('--date', '-dt', type=str, help='Date for weather and timestamp (e.g. 17.05.2026 or 2026-05-17)')
    parser.add_argument('--time', '-tm', type=str, help='Optional time for weather and timestamp (e.g. 18:30 or 18)')
    parser.add_argument('--no-weather', action='store_true', help='Disable fetching and showing weather data (only show timestamp)')
    parser.add_argument('--layout', '-l', type=str, default='portrait', choices=['portrait', 'landscape-plaque', 'gallery-plaque'], help='Layout format (default: portrait)')
    parser.add_argument('--no-card-title', action='store_true', default=None, help='Hide the title directly on the map (default for landscape-plaque and gallery-plaque)')
    parser.add_argument('--custom-note', type=str, default=None, help='Custom note to display on plaque layouts')
    parser.add_argument('--show-card-title', action='store_true', default=None, help='Explicitly show the title directly on the map')
    parser.add_argument('--config', type=str, help='Path to a JSON configuration file to prepopulate wizard inputs')
    
    args = parser.parse_args()
    
    # If no arguments provided or --wizard flag is used, run the wizard
    if len(os.sys.argv) == 1 or args.wizard or args.config:
        run_interactive_wizard(config_path=args.config)
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
            
        region = None
        if len(locations) == 1:
            coords = (locations[0].latitude, locations[0].longitude)
            print(f"✓ Ort eindeutig gefunden: {locations[0].address}")
            region = get_region_from_address(locations[0])
        else:
            # Ambiguity!
            if args.select_first:
                coords = (locations[0].latitude, locations[0].longitude)
                print(f"\033[93m⚠ Warnung: Mehrere Treffer für '{args.city}, {args.country}' gefunden!\033[0m")
                print(f"\033[93m  Wir verwenden den ersten Treffer: {locations[0].address}\033[0m")
                region = get_region_from_address(locations[0])
            else:
                print(f"\n✗ Error: Der Ort '{args.city}, {args.country}' ist nicht eindeutig! Es wurden {len(locations)} Übereinstimmungen gefunden:")
                top_locations = locations[:5]
                for idx, loc in enumerate(top_locations, 1):
                    print(f"  [{idx}] {loc.address}")
                print("\n💡 Tipp: Nutze den interaktiven Wizard (ohne Parameter oder mit -w) oder übergib '-y' / '--select-first', um den ersten Treffer zu erzwingen.")
                os.sys.exit(1)
                
        # Resolve no-card-title value
        no_card_title_val = None
        if args.no_card_title:
            no_card_title_val = True
        elif args.show_card_title:
            no_card_title_val = False
            
        output_file = generate_output_filename(args.city, args.theme, layout=args.layout)
        
        # Determine center coords
        if args.center_on_focus:
            center_coords = focus_coords
            print(f"✓ Kartenausschnitt wird auf den Fokus-Punkt zentriert: {center_coords}")
        else:
            center_coords = coords
            
        create_poster(args.city, args.country, center_coords, args.distance, output_file, focus_point=focus_coords, show_inset=args.show_inset, inset_position=args.inset_position, date_str=args.date, time_str=args.time, show_weather=not args.no_weather, layout=args.layout, no_card_title=no_card_title_val, region=region, custom_note=args.custom_note)
        
        print("\n" + "=" * 50)
        print("✓ Poster generation complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        os.sys.exit(1)
