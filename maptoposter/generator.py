import os
import time
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import osmnx as ox
from tqdm import tqdm
from PIL import Image, ImageChops, ImageEnhance
from geopy.geocoders import Nominatim
from shapely.geometry import Point as ShapelyPoint
from pyproj import Transformer

from maptoposter.theme import get_font_prop
from maptoposter.geocoding import get_region_from_address
from maptoposter.weather import parse_date_and_time, fetch_weather_data, GERMAN_MONTHS, WMO_WEATHER_CODES
from maptoposter.cache import cache_get, cache_set

POSTERS_DIR = "posters"

def generate_output_filename(city, theme_name, layout='portrait', output_format='png'):
    """
    Generate unique output filename with city, theme, and datetime.
    """
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(' ', '_')
    layout_suffix = f"_{layout}" if layout != 'portrait' else ""
    filename = f"{city_slug}_{theme_name}{layout_suffix}_{timestamp}.{output_format.lower()}"
    return os.path.join(POSTERS_DIR, filename)

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

def get_edge_colors_by_type(G, theme):
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
            color = theme['road_motorway']
        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']:
            color = theme['road_primary']
        elif highway in ['secondary', 'secondary_link']:
            color = theme['road_secondary']
        elif highway in ['tertiary', 'tertiary_link']:
            color = theme['road_tertiary']
        elif highway in ['residential', 'living_street', 'unclassified']:
            color = theme['road_residential']
        else:
            color = theme['road_default']
        
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

def is_latin_script(text):
    """
    Check if text is primarily Latin script.
    Used to determine if letter-spacing should be applied to city names.

    :param text: Text to analyze
    :return: True if text is primarily Latin script, False otherwise
    """
    if not text:
        return True

    latin_count = 0
    total_alpha = 0

    for char in text:
        if char.isalpha():
            total_alpha += 1
            # Latin Unicode ranges:
            # - Basic Latin: U+0000 to U+007F
            # - Latin-1 Supplement: U+0080 to U+00FF
            # - Latin Extended-A: U+0100 to U+017F
            # - Latin Extended-B: U+0180 to U+024F
            if ord(char) < 0x250:
                latin_count += 1

    # If no alphabetic characters, default to Latin (numbers, symbols, etc.)
    if total_alpha == 0:
        return True

    # Consider it Latin if >80% of alphabetic characters are Latin
    return (latin_count / total_alpha) > 0.8


def create_poster(city, country, point, dist, output_file, theme, focus_point=None, show_inset=False, inset_position='top-left', date_str=None, time_str=None, show_weather=True, layout='portrait', no_card_title=None, region=None, custom_note=None, use_paper_texture=False, font_family=None, width=None, height=None):
    print(f"\nGenerating map for {city}, {country}...")
    
    # Caching keys
    cache_key_g = f"osm_graph_{point[0]:.6f}_{point[1]:.6f}_{dist}"
    cache_key_water = f"osm_water_{point[0]:.6f}_{point[1]:.6f}_{dist}"
    cache_key_parks = f"osm_parks_{point[0]:.6f}_{point[1]:.6f}_{dist}"
    
    # Check cache first
    G = cache_get(cache_key_g)
    water = cache_get(cache_key_water)
    parks = cache_get(cache_key_parks)
    
    steps_to_do = 0
    if G is None: steps_to_do += 1
    if water is None: steps_to_do += 1
    if parks is None: steps_to_do += 1
    
    if steps_to_do == 0:
        print("✓ Alle Kartendaten wurden erfolgreich aus dem lokalen Cache geladen! (1-Sekunden-Boost)")
    else:
        print(f"Lade {steps_to_do} fehlende Datensätze von der Overpass API...")
        with tqdm(total=steps_to_do, desc="Fetching map data", unit="step", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
            if G is None:
                pbar.set_description("Downloading street network")
                G = ox.graph_from_point(point, dist=dist, dist_type='bbox', network_type='all')
                cache_set(cache_key_g, G)
                pbar.update(1)
                time.sleep(0.5)
                
            if water is None:
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
                except Exception as e:
                    print(f"⚠ Fehler beim Gewässer-Download: {e}")
                    water = None
                cache_set(cache_key_water, water)
                pbar.update(1)
                time.sleep(0.3)
                
            if parks is None:
                pbar.set_description("Downloading parks/green spaces")
                try:
                    parks = ox.features_from_point(point, tags={'leisure': 'park', 'landuse': 'grass'}, dist=dist)
                    if parks is not None and not parks.empty:
                        parks = parks[parks.geometry.type.isin(['Polygon', 'MultiPolygon'])]
                except Exception as e:
                    print(f"⚠ Fehler beim Park-Download: {e}")
                    parks = None
                cache_set(cache_key_parks, parks)
                pbar.update(1)
    
    print("✓ All data loaded successfully!")
    
    # 1.5 UTM Projection to avoid map warp and ensure perfectly circular focus points
    print("Projiziere Karte auf UTM (metrisches System)...")
    G_proj = ox.project_graph(G)
    G_crs = G_proj.graph['crs']
    
    # Transformer initialisieren und Referenzpunkte in UTM-Meter umrechnen
    transformer = Transformer.from_crs("epsg:4326", G_crs, always_xy=True)
    center_x, center_y = transformer.transform(point[1], point[0])
    
    focus_proj = None
    if focus_point is not None:
        focus_x, focus_y = transformer.transform(focus_point[1], focus_point[0])
        focus_proj = (focus_x, focus_y)
    
    if water is not None and not water.empty:
        water = water.to_crs(crs=G_crs)
    if parks is not None and not parks.empty:
        parks = parks.to_crs(crs=G_crs)

    # Determine if we should hide the card title directly on the map
    if no_card_title is None:
        should_hide_card_title = (layout in ['landscape-plaque', 'gallery-plaque'])
    else:
        should_hide_card_title = no_card_title

    # 2. Setup Plot
    print("Rendering map...")
    default_w, default_h = (12, 16) if layout not in ['landscape-plaque', 'gallery-plaque'] else (16 if layout == 'landscape-plaque' else 15, 10)
    w = width if width is not None else default_w
    h = height if height is not None else default_h
    
    # Cap both at 20 inches to prevent RAM bloat
    w = min(float(w), 20.0)
    h = min(float(h), 20.0)
    
    if layout in ['landscape-plaque', 'gallery-plaque']:
        fig = plt.figure(figsize=(w, h), facecolor=theme['bg'])
        # Map-Plot links (aspect ratio layout)
        ax = fig.add_axes([0.04, 0.04, 0.53, 0.92])
        ax.set_facecolor(theme['bg'])
        # Info-Plot rechts
        ax_info = fig.add_axes([0.61, 0.04, 0.35, 0.92])
        ax_info.set_facecolor(theme['bg'])
        ax_info.axis('off')
    else:
        fig, ax = plt.subplots(figsize=(w, h), facecolor=theme['bg'])
        ax.set_facecolor(theme['bg'])
        ax.set_position([0, 0, 1, 1])
    
    # 3. Plot Layers
    # Layer 1: Polygons
    if water is not None and not water.empty:
        water.plot(ax=ax, facecolor=theme['water'], edgecolor='none', zorder=1)
    if parks is not None and not parks.empty:
        parks.plot(ax=ax, facecolor=theme['parks'], edgecolor='none', zorder=2)
    
    # Layer 2: Roads with hierarchy coloring (uses UTM projected graph)
    print("Applying road hierarchy colors...")
    edge_colors = get_edge_colors_by_type(G_proj, theme)
    scale = 3.5 if layout == 'gallery-plaque' else 1.0
    edge_widths = [w * scale for w in get_edge_widths_by_type(G_proj)]
    
    ox.plot_graph(
        G_proj, ax=ax, bgcolor=theme['bg'],
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=edge_widths,
        show=False, close=False
    )
    
    # Ensure map borders are styled for plaque layout
    if layout in ['landscape-plaque', 'gallery-plaque']:
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(theme['text'])
            spine.set_linewidth(1.5 * scale)
            spine.set_alpha(0.8)
    
    # Set explicit axis limits to ensure the center coordinates are perfectly in the middle of the poster
    # Aspect Ratio dynamically calculated from actual axis coordinates in inches
    bbox = ax.get_position()
    fig_w, fig_h = fig.get_size_inches()
    ax_w_in = bbox.width * fig_w
    ax_h_in = bbox.height * fig_h
    ax_aspect = ax_h_in / ax_w_in
    
    if ax_aspect >= 1.0:
        half_w = dist
        half_h = dist * ax_aspect
    else:
        half_h = dist
        half_w = dist / ax_aspect
        
    ax.set_xlim(center_x - half_w, center_x + half_w)
    ax.set_ylim(center_y - half_h, center_y + half_h)
    
    # Layer 2.5: Fokus-Punkt (falls gesetzt)
    if focus_proj is not None:
        print("Platziere Fokus-Punkt auf der Karte (UTM)...")
        focus_color = theme.get('focus_color', '#E63946')
        focus_size = theme.get('focus_size', 350)
        focus_edge_color = theme.get('focus_edge_color', 'white')
        focus_edge_width = theme.get('focus_edge_width', 2.5)
        
        ax.scatter(focus_proj[0], focus_proj[1], 
                   color=focus_color, 
                   s=focus_size * (scale**2), 
                   zorder=9, 
                   edgecolor=focus_edge_color, 
                   linewidth=focus_edge_width * scale)
    
    # Layer 3: Gradients (Top and Bottom)
    create_gradient_fade(ax, theme['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, theme['gradient_color'], location='top', zorder=10)
    
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
    loaded_custom_fonts = None
    if font_family:
        try:
            from maptoposter.font_management import load_fonts as load_custom_fonts_mgr
            loaded_custom_fonts = load_custom_fonts_mgr(font_family)
        except Exception as e:
            print(f"⚠ Fehler beim Laden der Google-Schriftart '{font_family}': {e}")
            
    font_title_val = theme.get('font_title')
    font_body_val = theme.get('font_body')
    font_mono_val = theme.get('font_mono')
    
    if loaded_custom_fonts:
        font_title_bold = loaded_custom_fonts.get('bold')
        font_title_reg = loaded_custom_fonts.get('regular')
        font_title_light = loaded_custom_fonts.get('light')
        
        font_body_bold = loaded_custom_fonts.get('bold')
        font_body_reg = loaded_custom_fonts.get('regular')
        font_body_light = loaded_custom_fonts.get('light')
    else:
        font_title_bold = font_title_val
        font_title_reg = font_title_val
        font_title_light = font_title_val
        
        font_body_bold = font_body_val
        font_body_reg = font_body_val
        font_body_light = font_body_val
    
    # Calculate dynamic font size and letter spacing for bottom title to avoid truncation
    city_upper = city.upper()
    city_len = len(city_upper)
    
    if is_latin_script(city_upper):
        if city_len <= 8:
            spaced_city = "  ".join(list(city_upper))
            title_size = int(60 * scale)
        elif 8 < city_len <= 12:
            spaced_city = " ".join(list(city_upper))
            title_size = int(60 * (9.0 / city_len) * scale)
        else:
            spaced_city = " ".join(list(city_upper))
            title_size = int(max(30, 60 * (10.0 / city_len)) * scale)
    else:
        spaced_city = city_upper
        if city_len <= 5:
            title_size = int(60 * scale)
        else:
            title_size = int(max(30, 60 * (6.0 / city_len)) * scale)

    font_main = get_font_prop(font_title_bold, 'sans-serif', weight='bold', size=title_size)
    font_top = get_font_prop(font_title_bold, 'sans-serif', weight='bold', size=int(40 * scale))
    font_sub = get_font_prop(font_body_light if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else font_body_reg, 'sans-serif', 
                            weight='light' if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else 'normal', 
                            size=int(22 * scale))
    font_coords = get_font_prop(font_mono_val, 'monospace', size=int(14 * scale))
    font_attr = get_font_prop(font_mono_val, 'monospace', size=int(8 * scale))
    
    # Info Panel Fonts
    font_info_title = get_font_prop(font_title_bold, 'sans-serif', weight='bold', size=int(32 * scale))
    font_info_sub = get_font_prop(font_body_light if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else font_body_reg, 'sans-serif', 
                                  weight='light' if font_body_val in ['Futura', 'Avenir', 'Helvetica Neue'] else 'normal', 
                                  size=int(20 * scale))
    font_info_label = get_font_prop(font_body_reg, 'sans-serif', weight='normal', size=int(13 * scale))
    font_info_val = get_font_prop(font_title_bold, 'sans-serif', weight='bold', size=int(18 * scale))
    
    # Render Bottom text on Map only if not hidden
    if not should_hide_card_title:
        # --- BOTTOM TEXT ---
        ax.text(0.5, 0.14, spaced_city, transform=ax.transAxes,
                color=theme['text'], ha='center', fontproperties=font_main, zorder=11)
        
        ax.text(0.5, 0.10, country.upper(), transform=ax.transAxes,
                color=theme['text'], ha='center', fontproperties=font_sub, zorder=11)
        
        lat, lon = point
        coords = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
        if os.path.exists('create_map_poster.py'): # Dummy reference or actual formatting replacement
            pass
        if lon < 0:
            coords = coords.replace("E", "W")
        
        ax.text(0.5, 0.07, coords, transform=ax.transAxes,
                color=theme['text'], alpha=0.7, ha='center', fontproperties=font_coords, zorder=11)
        
        if weather_info_str:
            ax.text(0.5, 0.04, weather_info_str, transform=ax.transAxes,
                    color=theme['text'], alpha=0.7, ha='center', fontproperties=font_coords, zorder=11)
        
        ax.plot([0.4, 0.6], [0.125, 0.125], transform=ax.transAxes, 
                color=theme['text'], linewidth=1, zorder=11)
        
        # --- ATTRIBUTION (bottom right) ---
        ax.text(0.98, 0.02, "© OpenStreetMap contributors", transform=ax.transAxes,
                color=theme['text'], alpha=0.5, ha='right', va='bottom', 
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
                     color=theme['text'], ha='left', va='top', fontproperties=font_info_title, wrap=True)
        
        # Height adjustment for city title (if wrapped or long)
        y_pos -= 0.08
        if title_len > 18:
            y_pos -= 0.04
            
        # Draw Country Name
        ax_info.text(0.0, y_pos, country.upper(), transform=ax_info.transAxes,
                     color=theme['text'], ha='left', va='top', fontproperties=font_info_sub)
        
        y_pos -= 0.05
        
        # Draw a beautiful horizontal separator line in theme text color
        ax_info.plot([0.0, 0.9], [y_pos, y_pos], transform=ax_info.transAxes,
                     color=theme['text'], linewidth=1.5 * scale, alpha=0.8)
        
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
                         color=theme['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, region.upper(), transform=ax_info.transAxes,
                         color=theme['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 2: Zeitstempel / Date
        if datetime_val_str:
            ax_info.text(0.0, y_pos, "ZEITPUNKT", transform=ax_info.transAxes,
                         color=theme['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, datetime_val_str.upper(), transform=ax_info.transAxes,
                         color=theme['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 3: Klima & Wetter
        if weather_val_str:
            ax_info.text(0.0, y_pos, "KLIMA & WETTER", transform=ax_info.transAxes,
                         color=theme['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            ax_info.text(0.0, y_pos, weather_val_str.upper(), transform=ax_info.transAxes,
                         color=theme['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075
            
        # Stack 4: Custom Note / Kamera
        if custom_note:
            ax_info.text(0.0, y_pos, "KAMERA", transform=ax_info.transAxes,
                         color=theme['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
            y_pos -= 0.035
            
            # Ohne wrap=True, um Darstellungsprobleme (z.B. "blassere" Schrift in manchen Backends) zu vermeiden
            ax_info.text(0.0, y_pos, custom_note.upper(), transform=ax_info.transAxes,
                         color=theme['text'], ha='left', va='top', fontproperties=font_info_val)
            y_pos -= 0.075

        # Stack 5: Koordinaten / GPS
        lat, lon = point
        coords_val_str = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
        if lon < 0:
            coords_val_str = coords_val_str.replace("E", "W")
            
        ax_info.text(0.0, y_pos, "GPS-KOORDINATEN", transform=ax_info.transAxes,
                     color=theme['text'], alpha=0.6, ha='left', va='top', fontproperties=font_info_label)
        y_pos -= 0.035
        ax_info.text(0.0, y_pos, coords_val_str, transform=ax_info.transAxes,
                     color=theme['text'], ha='left', va='top', fontproperties=font_info_val)
        y_pos -= 0.075
        
        # Lower attribution text
        ax_info.text(0.0, 0.01, "© OpenStreetMap contributors", transform=ax_info.transAxes,
                     color=theme['text'], alpha=0.4, ha='left', va='bottom', fontproperties=font_attr)

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
                inset_ax = fig.add_axes([left, bottom, width, height], facecolor=theme['water'])
                
                # 4. Land plotten
                # Umrissfarbe: theme['text'], Füllung: theme.get('parks') oder theme['bg']
                land_color = theme.get('parks', theme['bg'])
                border_color = theme['text']
                gdf_country.plot(ax=inset_ax, facecolor=land_color, edgecolor=border_color, linewidth=0.5)
                
                # Exakte Anpassung auf die Bounding-Box, um interne Ränder zu eliminieren
                inset_ax.set_xlim(minx, maxx)
                inset_ax.set_ylim(miny, maxy)
                inset_ax.set_axis_off()
                
                # 5. Fokuspunkt/Kartenzentrum als roten Punkt einzeichnen
                lat, lon = point
                focus_color = theme.get('focus_color', '#B43B3B')
                inset_ax.scatter(lon, lat, color=focus_color, s=40 * (scale**2), zorder=5, edgecolor='white', linewidth=1 * scale)
                
                # 6. Achsen & Spines designen
                inset_ax.set_xticks([])
                inset_ax.set_yticks([])
                
                # Edler dünner Rahmen in Textfarbe
                for spine in inset_ax.spines.values():
                    spine.set_color(theme['text'])
                    spine.set_linewidth(0.8 * scale)
                    spine.set_alpha(0.8)
                    
                print("✓ Landeskarte (Inset) erfolgreich hinzugefügt!")
        except Exception as e:
            print(f"⚠ Warning: Landeskarte für {country} konnte nicht gerendert werden: {e}")

    # 5. Save
    print(f"Saving to {output_file}...")
    plt.savefig(output_file, dpi=300, facecolor=theme['bg'])
    plt.close()
    
    # 6. Apply Paper Texture if requested
    if use_paper_texture:
        if not output_file.lower().endswith('.png'):
            print("⚠ Washi-Papiertextur wird für Vektorformate (SVG/PDF) übersprungen, um die Vektoreigenschaften sauber zu halten.")
        else:
            texture_path = os.path.join('assets', 'paper_texture.png')
            if os.path.exists(texture_path):
                print("Applying Washi paper texture overlay...")
                try:
                    base_img = Image.open(output_file).convert("RGBA")
                    texture_img = Image.open(texture_path).convert("RGBA")
                    
                    # Resize texture to match base image exactly
                    texture_resized = texture_img.resize(base_img.size, Image.Resampling.LANCZOS)
                    
                    # Blend using multiply (preserves dark text, texturizes light areas)
                    blended = ImageChops.multiply(base_img, texture_resized)
                    
                    # Restore original brightness to preserve poster luminance (1.2 multiplier)
                    enhancer = ImageEnhance.Brightness(blended)
                    final_img = enhancer.enhance(1.2)
                    
                    # Save the processed image back
                    final_img.save(output_file, format="PNG")
                    print("✓ Paper texture successfully applied!")
                except Exception as e:
                    print(f"⚠ Warning: Could not apply paper texture: {e}")
            else:
                print(f"⚠ Warning: Paper texture file not found at {texture_path}. Skipping texture overlay.")

    print(f"✓ Done! Poster saved as {output_file}")
