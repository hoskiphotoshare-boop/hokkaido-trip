import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from deep_translator import GoogleTranslator

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

def get_weather_data():
    weather_payload = {}
    for name, coords in RESORTS.items():
        # Open-Meteo Free API: Requires no key, excellent for topographical weather
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,snowfall,wind_speed_10m&hourly=snow_depth&timezone=Asia%2FTokyo"
        
        try:
            response = requests.get(url)
            data = response.json()
            
            # Grab current weather and the latest hourly snow depth
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
    # Scrapes the daily bulletin from Niseko Avalanche Information
    url = "https://niseko.nadare.info/"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        latest_post = soup.find('div', class_='entry-content') or soup.find('article')
        if latest_post:
            # Grab the first few paragraphs (usually the core Japanese report)
            paragraphs = latest_post.find_all('p')
            text = " ".join([p.get_text(strip=True) for p in paragraphs[:4]])
            
            # Translate the scraped Japanese text into English
            try:
                translated_text = GoogleTranslator(source='auto', target='en').translate(text)
                return translated_text
            except Exception as e:
                return f"Translation failed: {text}\n(Error: {str(e)})"
                
        return "Bulletin structure changed or not found."
    except Exception as e:
        return f"Failed to fetch avalanche data: {str(e)}"


def get_cad_jpy_exchange():
    # ExchangeRate-API Free Tier
    url = "https://api.exchangerate-api.com/v4/latest/CAD"
    try:
        response = requests.get(url)
        data = response.json()
        return data.get("rates", {}).get("JPY", "N/A")
    except Exception as e:
        return f"Error: {str(e)}"

def build_payload():
    print("Fetching weather...")
    weather = get_weather_data()
    
    print("Fetching mountain safety...")
    safety = get_niseko_avalanche_bulletin()
    
    print("Fetching currency...")
    jpy_rate = get_cad_jpy_exchange()
    
    final_payload = {
        "last_updated_utc": datetime.utcnow().isoformat(),
        "currency": {
            "CAD_to_JPY": jpy_rate
        },
        "mountain_safety": {
            "niseko_avalanche_bulletin": safety
        },
        "resorts": weather
    }
    
    # Write to a public folder for Firebase Hosting to read
    import os
    os.makedirs('public', exist_ok=True)
    with open('public/data.json', 'w', encoding='utf-8') as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)
        
    print("Payload successfully generated at public/data.json")

if __name__ == "__main__":
    build_payload()
