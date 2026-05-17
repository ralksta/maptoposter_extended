import requests
from datetime import datetime

# English month names for premium styling
ENGLISH_MONTHS = {
    1: "JANUARY", 2: "FEBRUARY", 3: "MARCH", 4: "APRIL", 
    5: "MAY", 6: "JUNE", 7: "JULY", 8: "AUGUST", 
    9: "SEPTEMBER", 10: "OCTOBER", 11: "NOVEMBER", 12: "DECEMBER"
}

# WMO Weather Codes to Descriptions (English)
WMO_WEATHER_CODES = {
    0: "SUNNY",
    1: "MOSTLY CLEAR",
    2: "PARTLY CLOUDY",
    3: "CLOUDY",
    45: "FOGGY",
    48: "DEPOSITING RIME FOG",
    51: "LIGHT DRIZZLE",
    53: "DRIZZLE",
    55: "HEAVY DRIZZLE",
    56: "FREEZING DRIZZLE",
    57: "HEAVY FREEZING DRIZZLE",
    61: "LIGHT RAIN",
    63: "RAIN",
    65: "HEAVY RAIN",
    66: "LIGHT FREEZING RAIN",
    67: "HEAVY FREEZING RAIN",
    71: "LIGHT SNOWFALL",
    73: "SNOWFALL",
    75: "HEAVY SNOWFALL",
    77: "SNOW GRAINS",
    80: "LIGHT RAIN SHOWERS",
    81: "RAIN SHOWERS",
    82: "HEAVY RAIN SHOWERS",
    85: "LIGHT SNOW SHOWERS",
    86: "HEAVY SNOW SHOWERS",
    95: "THUNDERSTORM",
    96: "THUNDERSTORM WITH LIGHT HAIL",
    99: "THUNDERSTORM WITH HAIL",
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
            raise ValueError(f"Invalid date format: '{date_str}'. Allowed formats are e.g. 17.05.2026 or 2026-05-17.")

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
            raise ValueError(f"Invalid time format: '{time_str}'. Allowed formats are e.g. 18:30 or 18.")

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
    
    print(f"Fetching weather data from Open-Meteo ({'archive' if date_obj.date() < today else 'forecast'})...")
    
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    hourly = data.get("hourly", {})
    if not hourly or "time" not in hourly:
        raise ValueError("No hourly weather data present in the API response.")
        
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
        raise ValueError(f"Could not find a matching data point for hour {target_hour}.")
        
    temp = hourly["temperature_2m"][target_index]
    code = hourly["weather_code"][target_index]
    
    return temp, code
