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

# --- EXISTING FUNCTIONS ---

def get_weather_data():
    weather_payload = {}
    for name, coords in RESORTS.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,snowfall,wind_speed_10m&hourly=snow_depth&timezone=Asia%2FTokyo"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            snow_depth = hourly.get("snow_depth", [0])[-1] if hourly else 0
            
            weather_payload[name] = {
                "temp_celsius": current.get("temperature_2m", "N/A"),
                "recent_snowfall_cm": current.get("snowfall", "N/A"),
                "base_depth_cm": snow_depth,
                "wind_speed_kmh": current.get("wind_speed_10m", "N/A")
            }
        except Exception as e:
            weather_payload[name] = {"error": str(e)}
    return weather_payload

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

# --- NEW FUNCTIONS ---

def get_road_conditions(api_key=None):
    """Fetches travel times using OpenRouteService (OpenStreetMap data)."""
    api_key = api_key or os.getenv("ORS_API_KEY")
    
    if not api_key:
        return {"error": "ORS_API_KEY not found in environment variables."}
        
    # Coordinates in [longitude, latitude] format
    # Adjusted Lake Shikotsu from the lake's center to the Visitor Center on the shoreline
    coordinates = [
        [141.6811, 42.7875], # New Chitose Airport
        [141.4033, 42.7738], # Lake Shikotsu Onsen / Visitor Center
        [140.7554, 42.9018], # Kutchan
        [140.9947, 43.1907], # Otaru
        [142.4633, 43.4079], # Nakafurano
        [141.3545, 43.0618]  # Sapporo
    ]
    
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "coordinates": coordinates,
        "instructions": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"API Status {response.status_code}", "details": response.text}
            
        data = response.json()
        total_normal_mins = data["routes"][0]["summary"]["duration"] // 60
        total_distance_km = data["routes"][0]["summary"]["distance"] / 1000
        
        return {
            "normal_travel_time_mins": total_normal_mins,
            "total_distance_km": round(total_distance_km, 1),
            "note": "Open-source routing does not support real-time traffic delays."
        }
    except Exception as e:
        return {"error": str(e)}


def get_cts_disruptions():
    """Scrapes New Chitose Airport homepage for emergency alert banners."""
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
    """Scrapes SnowJapan's daily report for the latest headline/summary."""
    url = "https://www.snowjapan.com/japan-daily-snow-weather-reports/Niseko-Now"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the first two paragraphs of the main report if available
        report_body = soup.find('div', class_='report-text') or soup.find('div', class_='snow-report-content')
        
        if report_body:
            paragraphs = report_body.find_all('p')
            summary = " ".join([p.get_text(strip=True) for p in paragraphs[:2]])
            return summary if summary else "Report content is empty."
            
        # Fallback for Summer / Off-Season when the daily report elements are removed
        return "Daily resort news is currently unavailable (likely due to the summer off-season)."
        
    except Exception as e:
        return f"Failed to fetch resort news: {str(e)}"


# --- PAYLOAD BUILDER ---

def build_payload():
    print("Fetching weather...")
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
