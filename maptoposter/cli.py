import argparse
import os
import sys
import json
from datetime import datetime

from maptoposter.geocoding import get_coordinates, get_region_from_address
from maptoposter.theme import get_available_themes, load_theme
from maptoposter.generator import create_poster, generate_output_filename
from maptoposter.wizard import run_interactive_wizard

THEMES_DIR = "themes"

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

def parse_args_and_run():
    """Parses command line arguments and runs the poster generation or wizard."""
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
    parser.add_argument('--paper-texture', action='store_true', help='Apply a subtle Japanese Washi paper texture overlay to the final poster')
    parser.add_argument('--config', type=str, help='Path to a JSON configuration file to prepopulate wizard inputs')
    
    args = parser.parse_args()
    
    # If no arguments provided or --wizard flag is used, run the wizard
    if len(sys.argv) == 1 or args.wizard or args.config:
        run_interactive_wizard(config_path=args.config)
        sys.exit(0)
    
    # List themes if requested
    if args.list_themes:
        list_themes()
        sys.exit(0)
    
    # Validate required arguments
    if not args.city or not args.country:
        print("Error: --city and --country are required for CLI mode.\n")
        print("💡 Tipp: Starte das Skript einfach ohne Argumente oder mit -w, um den interaktiven Wizard zu starten!\n")
        print_examples()
        sys.exit(1)
    
    # Validate theme exists
    available_themes = get_available_themes()
    if args.theme not in available_themes:
        print(f"Error: Theme '{args.theme}' not found.")
        print(f"Available themes: {', '.join(available_themes)}")
        sys.exit(1)
    
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
            sys.exit(1)
            
    # Validate --center-on-focus has --focus
    if args.center_on_focus and not focus_coords:
        print("Error: --center-on-focus / -cf benötigt einen Fokuspunkt via --focus / -f!")
        sys.exit(1)
            
    # Get coordinates and generate poster
    try:
        locations = get_coordinates(args.city, args.country)
        if not locations:
            print(f"Error: Konnte keine Koordinaten für '{args.city}, {args.country}' finden! Bitte überprüfe die Schreibweise.")
            sys.exit(1)
            
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
                sys.exit(1)
                
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
            
        create_poster(
            city=args.city, 
            country=args.country, 
            point=center_coords, 
            dist=args.distance, 
            output_file=output_file, 
            theme=THEME, 
            focus_point=focus_coords, 
            show_inset=args.show_inset, 
            inset_position=args.inset_position, 
            date_str=args.date, 
            time_str=args.time, 
            show_weather=not args.no_weather, 
            layout=args.layout, 
            no_card_title=no_card_title_val, 
            region=region, 
            custom_note=args.custom_note, 
            use_paper_texture=args.paper_texture
        )
        
        print("\n" + "=" * 50)
        print("✓ Poster generation complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
