import os
import pickle
import hashlib

CACHE_DIR = "cache"

class CacheError(Exception):
    """Exception raised for errors in the caching layer."""
    pass

def _get_cache_filename(key: str) -> str:
    """
    Generates a unique MD5 hash for a given string key and returns the cache file path.
    """
    md5_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{md5_hash}.pkl")

def cache_get(key: str):
    """
    Retrieves data from the cache using a unique string key.
    Returns the deserialized object, or None if it doesn't exist.
    """
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)
        return None
        
    cache_file = _get_cache_filename(key)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            # If load fails, we gracefully treat it as a cache miss and log/ignore
            print(f"⚠ Cache read error for '{key}': {e}. Ignoring.")
            return None
    return None

def cache_set(key: str, data):
    """
    Saves data to the cache using a unique string key.
    """
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)
        
    cache_file = _get_cache_filename(key)
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        return True
    except Exception as e:
        print(f"⚠ Cache write error for '{key}': {e}.")
        return False
