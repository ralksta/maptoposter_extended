import time
from geopy.geocoders import Nominatim
from maptoposter.cache import cache_get, cache_set

def get_coordinates(city, country):
    """
    Fetches coordinates for a given city and country using geopy.
    Returns a list of Location objects or None if no results found.
    Includes caching and rate limiting to be respectful to the geocoding service.
    """
    cache_key = f"geocode_coords_{city.lower().strip()}_{country.lower().strip()}"
    cached_data = cache_get(cache_key)
    if cached_data is not None:
        print(f"✓ Geocoding cache hit for '{city}, {country}'")
        return cached_data

    print("Looking up coordinates...")
    geolocator = Nominatim(user_agent="city_map_poster")
    
    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)
    
    try:
        locations = geolocator.geocode(f"{city}, {country}", exactly_one=False, timeout=10, addressdetails=True, language='en')
        if locations:
            cache_set(cache_key, locations)
        return locations
    except Exception as e:
        raise RuntimeError(f"API Error during geocoding: {e}")

def search_location(query):
    """
    Searches coordinates and address details for a given query (address, landmark, coordinates).
    Returns a list of Location objects or None if no results found.
    """
    cache_key = f"geocode_search_{query.lower().strip()}"
    cached_data = cache_get(cache_key)
    if cached_data is not None:
        print(f"✓ Geocoding cache hit for search '{query}'")
        return cached_data

    print(f"Searching for '{query}'...")
    geolocator = Nominatim(user_agent="city_map_poster")
    
    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)
    
    try:
        locations = geolocator.geocode(query, exactly_one=False, timeout=10, addressdetails=True, language='en')
        if locations:
            cache_set(cache_key, locations)
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
