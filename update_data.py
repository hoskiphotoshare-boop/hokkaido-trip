import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import os

# 1. Master Ski Resort GPS Directory
RESORTS = {
    "Niseko Tokyu Grand Hirafu": {"lat": 42.86, "lon": 140.70},
    "Niseko Moiwa Ski Resort": {"lat": 42.84, "lon": 140.63},
    "Rusutsu Resort": {"lat": 42.75, "lon": 140.90},
    "Kiroro Snow World": {"lat": 43.07, "lon": 140.99},
    "Kamui Ski Links": {"lat": 43.83, "lon": 142.25},
    "Furano Ski Resort": {"lat": 43.33, "lon": 142.33},
    "Sapporo Teine": {"lat": 43.10, "lon": 141.19},
    "Sapporo Kokusai": {"lat": 43.07, "lon": 141.07}
}

# --- NEW AND UPDATED FUNCTIONS ---
def get_weather_data():
    """Fetches real-time weather, 24-hour snowfall, visibility, freezing levels, and daylight hours."""
    weather_payload = {}
    for name, coords in RESORTS.items():
        # MOVED: snow_depth and freezing_level_height to 'current'
        # ADDED: snowfall_sum to 'daily' for the 24-hour total
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,snowfall,wind_speed_10m,visibility,snow_depth,freezing_level_height&daily=sunrise,sunset,snowfall_sum&timezone=Asia%2FTokyo"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            current = data.get("current", {})
            daily = data.get("daily", {})
            
            # Open-Meteo returns snow_depth in meters; convert to cm
            raw_snow_depth_meters = current.get("snow_depth", 0)
            snow_depth_cm = round(raw_snow_depth_meters * 100) if raw_snow_depth_meters else 0
            
            weather_payload[name] = {
                "temp_celsius": current.get("temperature_2m", "N/A"),
                "24h_snowfall_cm": daily.get("snowfall_sum", ["N/A"])[0] if daily else "N/A",
                "base_depth_cm": snow_depth_cm,
                "wind_speed_kmh": current.get("wind_speed_10m", "N/A"),
                "visibility_meters": current.get("visibility", "N/A"),
                "freezing_level_m": current.get("freezing_level_height", "N/A"),
                "sunrise": daily.get("sunrise", ["N/A"])[0] if daily else "N/A",
                "sunset": daily.get("sunset", ["N/A"])[0] if daily else "N/A"
            }
        except Exception as e:
            weather_payload[name] = {"error": str(e)}
    return weather_payload

def get_jma_warnings():
    """Scans the JMA endpoints for Sapporo/Shiribeshi (016000) and Kamikawa/Furano (012000)."""
    # 010000 returns a 404 error, so we must query the sub-regions directly.
    area_codes = ["016000", "012000"]
    has_warnings = False
    
    try:
        for code in area_codes:
            url = f"https://www.jma.go.jp/bosai/warning/data/warning/{code}.json"
            response = requests.get(url, timeout=10)
            
            # Silently skip if a region endpoint is down instead of crashing
            if response.status_code != 200:
                continue 
                
            data = response.json()
            
            if isinstance(data, dict) and "areaTypes" in data:
                for area_type in data["areaTypes"]:
                    for area in area_type.get("areas", []):
                        for warning in area.get("warnings", []):
                            # Code "00" means normal/no warning. "解除" means a warning was just lifted.
                            if warning.get("code") != "00" and warning.get("status") != "解除":
                                has_warnings = True
                                break
                                
        if has_warnings:
            return "⚠️ ACTIVE WARNINGS: Severe weather advisories are currently in effect for your route. Please check the official JMA website."
        return "Normal. No active emergency warnings for your route."
    except Exception as e:
        return f"Failed to fetch JMA warnings: {str(e)}"

# --- EXISTING FUNCTIONS ---

def get_niseko_avalanche_bulletin():
    url = "https://niseko.nadare.info/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        latest_post = soup.find('div', class_='entry-content') or soup.find('article')
        if latest_post:
            paragraphs = latest_post.find_all('p')
            text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            return text
        return "Bulletin structure changed or not found."
    except Exception as e:
        return f"Failed to fetch avalanche data: {str(e)}"

def get_cad_jpy_exchange():
    url = "https://api.exchangerate-api.com/v4/latest/CAD"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get("rates", {}).get("JPY", "N/A")
    except Exception as e:
        return f"Error: {str(e)}"

def get_road_conditions(api_key=None):
    """Fetches segment-by-segment travel times and elevation data via OpenRouteService."""
    api_key = api_key or os.getenv("ORS_API_KEY")
    
    if not api_key:
        return {"error": "ORS_API_KEY not found in environment variables."}
        
    waypoints = [
        {"name": "New Chitose Airport", "coords": [141.6811, 42.7875]},
        {"name": "Lake Shikotsu Onsen", "coords": [141.4033, 42.7738]},
        {"name": "Kutchan", "coords": [140.7554, 42.9018]},
        {"name": "Otaru", "coords": [140.9947, 43.1907]},
        {"name": "Nakafurano", "coords": [142.4633, 43.4079]},
        {"name": "Sapporo", "coords": [141.3545, 43.0618]}
    ]
    
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "coordinates": [wp["coords"] for wp in waypoints],
        "elevation": True, 
        "instructions": True # Must be True to receive segment data
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            return {"error": f"API Status {response.status_code}", "details": response.text}
            
        route = response.json()["routes"][0]
        summary = route["summary"]
        
        # Parse individual legs between waypoints
        legs = []
        for i, segment in enumerate(route.get("segments", [])):
            legs.append({
                "from": waypoints[i]["name"],
                "to": waypoints[i+1]["name"],
                "distance_km": round(segment["distance"] / 1000, 1),
                "duration_mins": round(segment["duration"] / 60),
                "total_ascent_m": round(segment.get("ascent", 0)),
                "total_descent_m": round(segment.get("descent", 0))
            })
            
        return {
            "total_distance_km": round(summary["distance"] / 1000, 1),
            "total_duration_mins": round(summary["duration"] / 60),
            "total_ascent_m": round(summary.get("ascent", 0)),
            "total_descent_m": round(summary.get("descent", 0)),
            "legs": legs,
            "note": "Open-source routing does not support real-time traffic delays."
        }
    except Exception as e:
        return {"error": str(e)}

def get_cts_disruptions():
    url = "https://www.new-chitose-airport.jp/en/"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        alert = soup.find('div', class_='emergency') or soup.find('div', id='important_notice')
        if alert:
            return alert.get_text(strip=True)
        return "Normal operations. No emergency notices found."
    except Exception as e:
        return f"Failed to fetch airport status: {str(e)}"

def get_resort_news():
    url = "https://www.snowjapan.com/japan-daily-snow-weather-reports/Niseko-Now"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        report_body = soup.find('div', class_='report-text') or soup.find('div', class_='snow-report-content')
        if report_body:
            paragraphs = report_body.find_all('p')
            summary = " ".join([p.get_text(strip=True) for p in paragraphs[:2]])
            return summary if summary else "Report content is empty."
        return "Daily resort news is currently unavailable (likely due to the summer off-season)."
    except Exception as e:
        return f"Failed to fetch resort news: {str(e)}"

# --- PAYLOAD BUILDER ---

def build_payload():
    print("Fetching weather and daylight...")
    weather = get_weather_data()
    
    print("Fetching mountain safety...")
    safety = get_niseko_avalanche_bulletin()
    
    print("Fetching currency...")
    jpy_rate = get_cad_jpy_exchange()
    
    print("Fetching road conditions...")
    roads = get_road_conditions() 
    
    print("Fetching airport status...")
    airport = get_cts_disruptions()
    
    print("Fetching resort news...")
    news = get_resort_news()
    
    print("Fetching official JMA weather warnings...")
    jma_warnings = get_jma_warnings()
    
    final_payload = {
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
        "currency": {
            "CAD_to_JPY": jpy_rate
        },
        "logistics": {
            "cts_airport_notices": airport,
            "road_trip_status": roads
        },
        "mountain_safety": {
            "official_jma_warnings": jma_warnings,
            "niseko_avalanche_bulletin": safety,
            "latest_resort_news": news
        },
        "resorts": weather
    }
    
    os.makedirs('public', exist_ok=True)
    with open('public/data.json', 'w', encoding='utf-8') as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)
        
    print("Payload successfully generated at public/data.json")

if __name__ == "__main__":
    build_payload()
