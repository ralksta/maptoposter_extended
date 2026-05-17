import os
import json
import time

from maptoposter.geocoding import search_location, get_city_from_address, get_country_from_address, get_region_from_address
from maptoposter.theme import get_available_themes, load_theme, THEMES_DIR
from maptoposter.weather import parse_date_and_time
from maptoposter.generator import create_poster, generate_output_filename

def run_interactive_wizard(config_path=None):
    """
    Runs an interactive CLI wizard to gather parameters and generate a poster.
    Supports prepopulating and skipping questions via a config file.
    """
    print("\n" + "=" * 60)
    print("⚓️  Welcome to the City Map Poster Generator Wizard!  ⚓️")
    print("=" * 60)
    print("Let's create a beautiful map poster together. Just enter the information.\n")
    
    config = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✓ Config '{config_path}' loaded.")
        except Exception as e:
            print(f"⚠ Error loading config: {e}")

    final_config = {}

    def wizard_input(prompt, key):
        if key in config:
            val = str(config[key])
            print(f"{prompt}{val}  (From Config)")
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
    
    # 1. Location or GPS coordinates choice
    print("👉 Do you want to search for a location or enter GPS coordinates directly?")
    print("  [1] Search for a location (e.g., 'Hamburg') (Default)")
    print("  [2] Enter GPS coordinates manually (Latitude / Longitude)")
    
    manual_coords = False
    while True:
        choice = wizard_input("Select an option [1-2] (Default: 1): ", "coord_input_mode")
        if not choice or choice == '1':
            manual_coords = False
            break
        elif choice == '2':
            manual_coords = True
            break
        print("⚠ Invalid choice. Please select 1 or 2.")
        
    if manual_coords:
        while True:
            lat_input = wizard_input("👉 Latitude (e.g., 53.5511): ", "manual_latitude")
            try:
                lat = float(lat_input)
                break
            except ValueError:
                print("⚠ Please enter a valid number for latitude.")
        while True:
            lon_input = wizard_input("👉 Longitude (e.g., 9.9937): ", "manual_longitude")
            try:
                lon = float(lon_input)
                break
            except ValueError:
                print("⚠ Please enter a valid number for longitude.")
        coords = (lat, lon)
        print(f"✓ Manual coordinates set: {coords}\n")
    else:
        # Search for location
        while True:
            query = wizard_input("👉 Which location, landmark, or address do you want to show? (e.g., 'Tokyo', 'Elbphilharmonie Hamburg'): ", "query")
            if not query:
                print("⚠ A location is required! Please enter a name.")
                continue
                
            try:
                locations = search_location(query)
                if not locations:
                    print(f"\n⚠ Error: Could not find '{query}'! Please check your input.\n")
                    continue
                    
                if len(locations) == 1:
                    selected_loc = locations[0]
                    coords = (selected_loc.latitude, selected_loc.longitude)
                    resolved_address = selected_loc.address
                    print(f"✓ Found: {resolved_address}")
                    print(f"✓ Coordinates: {coords[0]}, {coords[1]}\n")
                    break
                else:
                    # Multiple matches!
                    print(f"\n🔎 Found {len(locations)} matching locations. Which one do you mean?")
                    top_locations = locations[:5]
                    for idx, loc in enumerate(top_locations, 1):
                        print(f"  [{idx}] {loc.address}")
                    print("  [0] None of these (refine search)")
                    
                    while True:
                        choice = wizard_input(f"Select an option [1-{len(top_locations)}] or 0 (Default: 1): ", "location_choice")
                        if not choice:
                            choice_idx = 1
                        else:
                            try:
                                choice_idx = int(choice)
                            except ValueError:
                                print("⚠ Please enter a number!")
                                continue
                                
                        if choice_idx == 0:
                            print("\nUnderstood, let's refine the search.\n")
                            break  # Breaks inner selection loop, goes back to query input
                        elif 1 <= choice_idx <= len(top_locations):
                            selected_loc = top_locations[choice_idx - 1]
                            coords = (selected_loc.latitude, selected_loc.longitude)
                            resolved_address = selected_loc.address
                            print(f"✓ Selected: {resolved_address}")
                            print(f"✓ Coordinates: {coords[0]}, {coords[1]}\n")
                            break
                            
                    if choice_idx != 0:
                        break  # Break outer lookup loop
                        
            except Exception as e:
                print(f"\n⚠ Error searching for location: {e}. Please try again.\n")

    # 2. Focus Marker choice
    print("👉 Do you want to draw a red focus point marker at this location?")
    print("  [1] No, clean map centered on this location (Default - ideal for city maps)")
    print("  [2] Yes, place a red focus point marker at the coordinates")
    
    while True:
        choice = wizard_input("Select an option [1-2] (Default: 1): ", "focus_choice")
        if not choice or choice == '1':
            actual_focus_coords = None
            print("✓ Map will be centered, clean without a red marker.\n")
            break
        if choice == '2':
            actual_focus_coords = coords
            print("✓ Red focus point marker will be drawn at the coordinates!\n")
            break
        print("⚠ Invalid choice. Please select 1 or 2.")

    # 3. Title & Subtitle with suggestions
    detected_city = get_city_from_address(selected_loc)
    detected_country = get_country_from_address(selected_loc)
    
    print("👉 Let's define the labels (title & subtitle) for your poster.")
    
    while True:
        city_prompt = f"👉 Main title for the poster (Default: {detected_city}): " if detected_city else "👉 Main title for the poster (e.g., Hamburg): "
        city_input = wizard_input(city_prompt, "city")
        if not city_input:
            city = detected_city
        else:
            city = city_input
        if city:
            break
        print("⚠ A main title is required!")
        
    country_prompt = f"👉 Subtitle for the poster (Default: {detected_country}): " if detected_country else "👉 Subtitle for the poster (e.g., Germany): "
    country_input = wizard_input(country_prompt, "country")
    if not country_input:
        country = detected_country
    else:
        country = country_input

    # 4. Theme Selection
    available_themes = get_available_themes()
    print("\n👉 Which color scheme (theme) would you like?")
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
            choice = wizard_input(f"Choose a number [1-{len(available_themes)}] (Default: {default_theme_idx} -> {default_theme}): ", "theme_choice")
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
                
            print(f"⚠ Invalid choice. Please choose a number between 1 and {len(available_themes)} or type the name directly.")
    else:
        print("  (No themes found in folder. Using default 'feature_based')")
        theme = "feature_based"

    # 5. Distance (Map Radius) Selection
    print("\n👉 What map radius (in meters) would you like to show?")
    print("  [1] Focus on city center / Tight zoom (approx. 5,000m)")
    print("  [2] Focus on city / Medium zoom (approx. 10,000m) -- Recommended!")
    print("  [3] Whole metropolis / Wide zoom (approx. 20,000m)")
    print("  [4] Custom / Enter manually in meters")
    
    while True:
        dist_choice = wizard_input("Select an option [1-4] (Default: 2 -> 10000m): ", "dist_choice")
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
                custom_dist = wizard_input("Enter the radius in meters (e.g., 12000): ", "custom_distance")
                try:
                    distance = int(custom_dist)
                    if distance > 0:
                        break
                    print("⚠ The radius must be greater than 0.")
                except ValueError:
                    print("⚠ Please enter a valid number.")
            break
        else:
            print("⚠ Invalid choice. Please choose an option from 1 to 4.")
            
    # 6. Country locator map (Inset-Map) choice
    show_inset = False
    inset_position = 'top-left'
    
    print("\n👉 Do you want to display a small country locator map (inset map) in a corner?")
    print("  [1] No (Default)")
    print("  [2] Yes, display inset map")
    
    while True:
        choice = wizard_input("Select an option [1-2] (Default: 1): ", "inset_choice")
        if not choice or choice == '1':
            show_inset = False
            print("✓ No inset map on the poster.\n")
            break
        if choice == '2':
            show_inset = True
            print("✓ Inset map will be drawn on the poster!\n")
            
            print("👉 In which corner should the inset map be placed?")
            print("  [1] Top-Left (Default)")
            print("  [2] Top-Right")
            print("  [3] Bottom-Left (Above the text)")
            print("  [4] Bottom-Right (Above the text)")
            
            while True:
                pos_choice = wizard_input("Select an option [1-4] (Default: 1): ", "inset_position")
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
                    print("⚠ Invalid choice. Please select an option from 1 to 4.")
            
            print(f"✓ Inset map position set to: {inset_position}\n")
            break
        print("⚠ Invalid choice. Please choose 1 or 2.")

    # 7. Weather & Timestamp choice
    date_str = None
    time_str = None
    show_weather = True

    print("\n👉 Do you want to display a timestamp and weather info on the poster?")
    print("  [1] No (Default)")
    print("  [2] Yes, enter date/time and load weather data")

    while True:
        choice = wizard_input("Select an option [1-2] (Default: 1): ", "weather_time_choice")
        if not choice or choice == '1':
            date_str = None
            time_str = None
            show_weather = False
            print("✓ No timestamp or weather data on the poster.\n")
            break
        if choice == '2':
            # Ask for date
            while True:
                d_input = wizard_input("👉 Enter date (e.g., '17.05.2026' or '2026-05-17'): ", "date_str")
                if not d_input:
                    print("⚠ A date is required for the timestamp!")
                    continue
                try:
                    parse_date_and_time(d_input, None)
                    date_str = d_input
                    break
                except ValueError as ve:
                    print(f"⚠ {ve} Please try again.")
            
            # Ask for time
            t_input = wizard_input("👉 Enter time optional (e.g., '18:30' or leave empty for midday): ", "time_str")
            if t_input:
                while True:
                    try:
                        parse_date_and_time(date_str, t_input)
                        time_str = t_input
                        break
                    except ValueError as ve:
                        print(f"⚠ {ve} Please try again.")
                        t_input = wizard_input("👉 Enter time optional: ", "time_str")
                        if not t_input:
                            break

            # Ask for weather
            weather_choice = wizard_input("👉 Fetch and display weather details (temp & cloud cover)? [Y/n] (Default: Y): ", "show_weather_choice").lower()
            if weather_choice in ['', 'y', 'yes']:
                show_weather = True
                print("✓ Weather data will be fetched from Open-Meteo!")
            else:
                show_weather = False
                print("✓ Only timestamp will be displayed (no weather).")
            print()
            break
        print("⚠ Invalid choice. Please choose 1 or 2.")

    # 8. Layout Format Choice
    layout = 'portrait'
    no_card_title = None

    print("\n👉 Which layout format should your poster have?")
    print("  [1] Classic Portrait (Default - ideal for wall framing)")
    print("  [2] Gallery Info Plaque (Sleek 16:10 landscape with info panel on the right)")
    
    while True:
        choice = wizard_input("Select an option [1-2] (Default: 1): ", "layout_choice")
        if not choice or choice == '1':
            layout = 'portrait'
            print("✓ Layout set to: Classic Portrait (portrait)\n")
            break
        if choice == '2':
            layout = 'landscape-plaque'
            print("✓ Layout set to: Gallery Info Plaque (landscape)\n")
            
            # Ask about title directly on the map for plaque layout
            print("👉 Would you like to also draw a title directly on the map portion?")
            print("  [1] No, keep the map clean (Default - recommended)")
            print("  [2] Yes, show title on the map as well")
            while True:
                title_choice = wizard_input("Select an option [1-2] (Default: 1): ", "title_choice")
                if not title_choice or title_choice == '1':
                    no_card_title = True
                    print("✓ Map remains clean without a title.\n")
                    break
                elif title_choice == '2':
                    no_card_title = False
                    print("✓ Title will also be drawn on the map.\n")
                    break
                else:
                    print("⚠ Please select 1 or 2.")
            break
        print("⚠ Please select 1 or 2.")

    # 9. Custom Note for Plaque Layout
    custom_note = None
    if layout in ['landscape-plaque', 'gallery-plaque']:
        print("\n👉 Do you want to add custom camera details (free text)? (Optional)")
        note_input = wizard_input("Enter your camera details (leave empty for none): ", "custom_note")
        if note_input.strip():
            custom_note = note_input
            print("✓ Camera details added.")
            
    # 10. Paper Texture Overlay
    use_paper_texture = False
    print("\n👉 Do you want to apply a fine Japanese Washi paper texture overlay to the poster?")
    texture_choice = wizard_input("Apply paper texture? [y/N] (Default: N): ", "use_paper_texture").lower()
    if texture_choice in ['y', 'yes', 'true', '1']:
        use_paper_texture = True
        print("✓ Washi paper texture will be applied.\n")
    else:
        print("✓ Poster remains clean (no texture).\n")

    # 11. Output File Format Choice
    output_format = 'png'
    print("\n👉 Which file format should your poster have?")
    print("  [1] PNG (High-resolution raster image - Default)")
    print("  [2] SVG (Vector graphic - Perfect for infinite scaling)")
    print("  [3] PDF (Print-ready document - Ideal for professional printing)")
    
    while True:
        fmt_choice = wizard_input("Select an option [1-3] (Default: 1): ", "format")
        if not fmt_choice or fmt_choice == '1' or fmt_choice.lower() == 'png':
            output_format = 'png'
            print("✓ Format set to: PNG\n")
            break
        elif fmt_choice == '2' or fmt_choice.lower() == 'svg':
            output_format = 'svg'
            print("✓ Format set to: SVG\n")
            break
        elif fmt_choice == '3' or fmt_choice.lower() == 'pdf':
            output_format = 'pdf'
            print("✓ Format set to: PDF\n")
            break
        else:
            print("⚠ Please select 1, 2, or 3, or type png, svg, pdf.")

    # 12. Google Font Selection
    font_family = None
    print("\n👉 Do you want to use a custom Google Font?")
    print("  Leave empty to use the theme's default font.")
    font_choice = wizard_input("Enter the name of the Google Font (e.g., 'Noto Sans JP', 'Montserrat' or leave empty): ", "font_family")
    if font_choice.strip():
        font_family = font_choice.strip()
        print(f"✓ Font set to: {font_family}\n")
    else:
        font_family = None
        print("✓ Using default font from theme.\n")

    # 13. Custom Poster Dimensions (in inches)
    width = None
    height = None
    print("\n👉 Do you want to set custom dimensions for your poster (in inches)?")
    print("  (Leave empty to use the default layout aspect ratio.)")
    print("  ⚠ Note: For stability reasons, the width and height are capped at a maximum of 20.0 inches!")
    
    while True:
        width_choice = wizard_input("Width in inches (e.g., 12.0 or leave empty): ", "width")
        if not width_choice.strip():
            width = None
            break
        try:
            w_val = float(width_choice)
            if w_val <= 0:
                print("⚠ The width must be greater than 0.")
                continue
            if w_val > 20.0:
                print(f"\033[93m⚠ Warning: {w_val} inches exceeds the limit! Capping at 20.0 inches.\033[0m")
                width = 20.0
            else:
                width = w_val
            break
        except ValueError:
            print("⚠ Please enter a valid number for the width.")
            
    while True:
        height_choice = wizard_input("Height in inches (e.g., 18.0 or leave empty): ", "height")
        if not height_choice.strip():
            height = None
            break
        try:
            h_val = float(height_choice)
            if h_val <= 0:
                print("⚠ The height must be greater than 0.")
                continue
            if h_val > 20.0:
                print(f"\033[93m⚠ Warning: {h_val} inches exceeds the limit! Capping at 20.0 inches.\033[0m")
                height = 20.0
            else:
                height = h_val
            break
        except ValueError:
            print("⚠ Please enter a valid number for the height.")
            
    if width is not None or height is not None:
        print(f"✓ Custom dimensions set: {width if width is not None else 'Default'} x {height if height is not None else 'Default'} inches\n")
    else:
        print("✓ Using default layout aspect ratio.\n")

    print("\n" + "=" * 50)
    print("Alright! Here is your setup roadmap:")
    print(f"  📍 Main Title:  {city}")
    print(f"  📍 Subtitle:    {country}")
    print(f"  🎨 Theme:       {theme}")
    print(f"  📐 Radius:      {distance} meters")
    if actual_focus_coords is None:
        print("  🔴 Focus Point: None (clean map centered)")
    else:
        print(f"  🔴 Focus Point: {actual_focus_coords[0]:.4f}, {actual_focus_coords[1]:.4f} (Centered with red marker)")
    if show_inset:
        print(f"  🗺 Locator Map: Yes (Position: {inset_position})")
    else:
        print("  🗺 Locator Map: No")
    if date_str:
        t_str = f" at {time_str}" if time_str else ""
        w_str = " (with weather)" if show_weather else " (no weather)"
        print(f"  📅 Timestamp:   {date_str}{t_str}{w_str}")
    else:
        print("  📅 Timestamp:   No")
    print(f"  📐 Layout:      {'Classic Portrait (portrait)' if layout == 'portrait' else 'Gallery Info Plaque (landscape)'}")
    if layout == 'landscape-plaque':
        print(f"  📛 Map Title:   {'Clean (Hidden)' if no_card_title else 'Visible'}")
    if custom_note:
        print(f"  📷 Camera:      {custom_note}")
    print(f"  📝 Paper Overlay:{'Yes (Washi)' if use_paper_texture else 'No (Clean)'}")
    print(f"  💾 File Format: {output_format.upper()}")
    print(f"  🔤 Font Family: {font_family if font_family else 'Theme Default'}")
    print(f"  📏 Dimensions:  {f'{width} x {height} inches' if (width is not None or height is not None) else 'Default'}")
    print("=" * 50 + "\n")
    
    confirm = wizard_input("Generate the poster with this configuration? [Y/n]: ", "confirm_generation").lower()
    if confirm in ['', 'y', 'yes']:
        # Load theme
        theme_data = load_theme(theme)
        
        try:
            region = get_region_from_address(selected_loc)
            output_file = generate_output_filename(city, theme, layout=layout, output_format=output_format)
            create_poster(city, country, coords, distance, output_file, theme=theme_data, focus_point=actual_focus_coords, show_inset=show_inset, inset_position=inset_position, date_str=date_str, time_str=time_str, show_weather=show_weather, layout=layout, no_card_title=no_card_title, region=region, custom_note=custom_note, use_paper_texture=use_paper_texture, font_family=font_family, width=width, height=height)
            
            print("\n" + "=" * 50)
            print("✓ Poster generation completed successfully!")
            print(f"Your poster file is saved at: {output_file}")
            print("=" * 50)
            
            save_name = wizard_input("\n👉 Do you want to save this configuration? [Name/n] (Default: n): ", "save_config_name")
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
                print(f"✓ Configuration saved as '{save_path}'")
            
        except Exception as e:
            print(f"\n✗ Error during generation: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Generation cancelled.")
