from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="maptoposter_extended_test")

def test_language(lang):
    print(f"\n--- Testing language: {lang} ---")
    try:
        locs = geolocator.geocode("Kada, Japan", addressdetails=True, timeout=10, language=lang)
        if locs:
            print(f"Address: {locs.address}")
            print(f"Raw address: {locs.raw.get('address', {})}")
        else:
            print("No result.")
    except Exception as e:
        print(f"Error: {e}")

test_language("de")
test_language("en")
test_language(None)
