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
            
    # 10. Paper Texture
    use_paper_texture = False
    print("\n👉 Möchtest du eine feine japanische Washi-Papierstruktur über das Poster legen?")
    texture_choice = wizard_input("Texture anwenden? [y/N] (Standard: N): ", "use_paper_texture").lower()
    if texture_choice in ['y', 'yes', 'ja', 'true', '1']:
        use_paper_texture = True
        print("✓ Washi-Papierstruktur wird angewendet.\n")
    else:
        print("✓ Poster bleibt clean (ohne Textur).\n")

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
    print(f"  📝 Papier-Textur: {'Ja (Washi)' if use_paper_texture else 'Nein (Clean)'}")
    print("=" * 50 + "\n")
    
    confirm = wizard_input("Sollen wir das Poster so generieren? [Y/n]: ", "confirm_generation").lower()
    if confirm in ['', 'y', 'yes', 'ja']:
        # Load theme
        theme_data = load_theme(theme)
        
        try:
            region = get_region_from_address(selected_loc)
            output_file = generate_output_filename(city, theme, layout=layout)
            create_poster(city, country, coords, distance, output_file, theme=theme_data, focus_point=actual_focus_coords, show_inset=show_inset, inset_position=inset_position, date_str=date_str, time_str=time_str, show_weather=show_weather, layout=layout, no_card_title=no_card_title, region=region, custom_note=custom_note, use_paper_texture=use_paper_texture)
            
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
