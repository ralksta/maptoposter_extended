import requests
from datetime import datetime

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
