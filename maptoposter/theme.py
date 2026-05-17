import os
import json
from matplotlib.font_manager import FontProperties

THEMES_DIR = "themes"
FONTS_DIR = "fonts"

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

def get_font_prop(font_val, default_family='sans-serif', **kwargs):
    """
    Get FontProperties based on font_val (family name or ttf/otf file path) and kwargs.
    """
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
