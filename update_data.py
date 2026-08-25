import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import os

try:
    from google.colab import userdata
    ORS_API_KEY = userdata.get('ORS_API_KEY')
except Exception:
    ORS_API_KEY = os.getenv('ORS_API_KEY')

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

# 2. Recommended Onsens
ONSENS = {
    "Goshiki Onsen (Niseko)": {"lat": 42.887, "lon": 140.635},
    "Fukiage Onsen (Furano)": {"lat": 43.435, "lon": 142.645},
    "Hoheikyo Onsen (Sapporo)": {"lat": 42.946, "lon": 141.164}
}

# --- NEW AND UPDATED FUNCTIONS ---
def get_weather_data():
    """Fetches real-time weather, 24-hour snowfall, visibility, freezing levels, cloud cover, UV, and daylight hours."""
    weather_payload = {}
    for name, coords in RESORTS.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,snowfall,wind_speed_10m,visibility,snow_depth,freezing_level_height,cloud_cover,uv_index&daily=sunrise,sunset,snowfall_sum&timezone=Asia%2FTokyo"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            current = data.get("current", {})
            daily = data.get("daily", {})

            raw_snow_depth_meters = current.get("snow_depth", 0)
            snow_depth_cm = round(raw_snow_depth_meters * 100) if raw_snow_depth_meters else 0

            weather_payload[name] = {
                "temp_celsius": current.get("temperature_2m", "N/A"),
                "24h_snowfall_cm": daily.get("snowfall_sum", ["N/A"])[0] if daily else "N/A",
                "base_depth_cm": snow_depth_cm,
                "wind_speed_kmh": current.get("wind_speed_10m", "N/A"),
                "visibility_meters": current.get("visibility", "N/A"),
                "freezing_level_m": current.get("freezing_level_height", "N/A"),
                "cloud_cover_percent": current.get("cloud_cover", "N/A"),
                "uv_index": current.get("uv_index", "N/A"),
                "sunrise": daily.get("sunrise", ["N/A"])[0] if daily else "N/A",
                "sunset": daily.get("sunset", ["N/A"])[0] if daily else "N/A"
            }
        except Exception as e:
            weather_payload[name] = {"error": str(e)}
    return weather_payload

def get_jma_warnings():
    """Scans the JMA endpoints for Sapporo/Shiribeshi (016000) and Kamikawa/Furano (012000)."""
    area_codes = ["016000", "012000"]
    has_warnings = False

    try:
        for code in area_codes:
            url = f"https://www.jma.go.jp/bosai/warning/data/warning/{code}.json"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                continue

            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                data = data[0] # Handle case if array is returned.

            if isinstance(data, dict) and "areaTypes" in data:
                for area_type in data["areaTypes"]:
                    for area in area_type.get("areas", []):
                        for warning in area.get("warnings", []):
                            if warning.get("code") != "00" and warning.get("status") != "解除":
                                has_warnings = True
                                break

        if has_warnings:
            return "⚠️ ACTIVE WARNINGS: Severe weather advisories are currently in effect for your route. Please check the official JMA website."
        return "Normal. No active emergency warnings for your route."
    except Exception as e:
        return f"Failed to fetch JMA warnings: {str(e)}"

def get_jma_earthquakes():
    """Fetches the most recent earthquake data from the JMA."""
    url = "https://www.jma.go.jp/bosai/quake/data/list.json"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data and len(data) > 0:
            latest = data[0]
            return {
                "time": latest.get("at", "N/A"),
                "epicenter": latest.get("anm", "N/A"),
                "magnitude": latest.get("mag", "N/A"),
                "max_seismic_intensity": latest.get("maxi", "N/A")
            }
        return "No recent earthquakes found."
    except Exception as e:
        return f"Failed to fetch earthquake data: {str(e)}"

def get_jr_hokkaido_status():
    """Fetches a summary of JR Hokkaido train operations."""
    url = "https://www3.jrhokkaido.co.jp/webunkou/"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        alert_boxes = soup.find_all('div', class_='alert_box')
        if alert_boxes:
            return "⚠️ Train disruptions reported on JR Hokkaido. Check official site."
        return "Operations appear normal based on homepage check."
    except Exception as e:
        return f"Failed to fetch JR Hokkaido status: {str(e)}"

def get_lift_status():
    """Fetches live lift and run status for all target ski resorts via web scraping."""
    statuses = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 1. Niseko United Central Page (Covers Grand Hirafu & Others)
    niseko_url = "https://www.niseko.ne.jp/en/niseko-lift-status/"
    niseko_data = {}
    try:
        res = requests.get(niseko_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            resort_containers = soup.find_all('li', id=lambda x: x and x.startswith('liftList_tag_'))
            for container in resort_containers:
                h3 = container.find('h3')
                if not h3:
                    continue
                resort_name = h3.get_text(strip=True).upper()

                open_lifts = 0
                total_lifts = 0

                lift_uls = container.find_all('ul', id=True)
                for ul in lift_uls:
                    if 'liftListHeader' in ul.get('class', []):
                        continue
                    lis = ul.find_all('li')
                    if len(lis) >= 4:
                        total_lifts += 1
                        img = lis[3].find('img', class_='liftStatusPic')
                        if img:
                            src = img.get('src', '')
                            if 'OPN_PICT' in src or 'open' in src.lower():
                                open_lifts += 1

                niseko_data[resort_name] = f"{open_lifts}/{total_lifts} Lifts"
    except Exception as e:
        print(f"Error fetching Niseko: {e}")

    # Map to our standard names + add all Niseko United specific names
    statuses["Niseko Tokyu Grand Hirafu"] = {
        "lifts_open": niseko_data.get("GRAND HIRAFU", "N/A"),
        "runs_open": "N/A",
        "status": "Live Data Parsed" if "GRAND HIRAFU" in niseko_data else "Error parsing"
    }
    statuses["Niseko Annupuri"] = {
        "lifts_open": niseko_data.get("ANNUPURI", "N/A"),
        "runs_open": "N/A",
        "status": "Live Data Parsed" if "ANNUPURI" in niseko_data else "Error parsing"
    }
    statuses["Niseko Village"] = {
        "lifts_open": niseko_data.get("NISEKO VILLAGE", "N/A"),
        "runs_open": "N/A",
        "status": "Live Data Parsed" if "NISEKO VILLAGE" in niseko_data else "Error parsing"
    }
    statuses["Niseko Hanazono"] = {
        "lifts_open": niseko_data.get("HANAZONO", "N/A"),
        "runs_open": "N/A",
        "status": "Live Data Parsed" if "HANAZONO" in niseko_data else "Error parsing"
    }

    # 2. Kiroro Snow World
    kiroro_url = "https://www.kiroro.co.jp/snow_report/"
    kiroro_status = "N/A"
    kiroro_lifts = "N/A"
    kiroro_runs = "N/A"
    try:
        res = requests.get(kiroro_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            open_lifts = soup.find_all(class_='status-open')
            if open_lifts:
                kiroro_lifts = open_lifts[0].get_text(strip=True) if len(open_lifts) > 0 else "N/A"
                kiroro_runs = open_lifts[1].get_text(strip=True) if len(open_lifts) > 1 else "N/A"
                kiroro_status = "Live Data Parsed"
    except Exception as e:
         kiroro_status = f"Error: {e}"

    statuses["Kiroro Snow World"] = {
        "lifts_open": kiroro_lifts,
        "runs_open": kiroro_runs,
        "status": kiroro_status
    }

    # 3. Manual Check Resorts
    manual_resorts = [
        "Niseko Moiwa Ski Resort",
        "Rusutsu Resort",
        "Kamui Ski Links",
        "Furano Ski Resort",
        "Sapporo Teine",
        "Sapporo Kokusai"
    ]
    for r in manual_resorts:
        statuses[r] = {
            "lifts_open": "Manual Check Req.",
            "runs_open": "N/A",
            "status": "Web Scraping Blocked or Dynamic Content"
        }

    return statuses

# --- EXISTING FUNCTIONS ---

def get_niseko_avalanche_bulletin():
    url = "https://niseko.nadare.info/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        latest_post = soup.find('div', class_='entry-content') or soup.find('article')
        if latest_post:
            paragraphs = latest_post.find_all('p')
            text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            return text

        return "Bulletin structure changed or not found."

    except requests.exceptions.Timeout:
        return "Avalanche bulletin is currently unreachable (likely offline for the summer off-season)."
    except Exception as e:
        return f"Failed to fetch avalanche data: {str(e)}"

def get_cad_jpy_exchange():
    end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')

    history_url = f"https://api.frankfurter.app/{start_date}..{end_date}?from=CAD&to=JPY"
    latest_url = "https://api.frankfurter.app/latest?from=CAD&to=JPY"

    payload = {
        "latest_rate": "N/A",
        "7_day_history": []
    }

    try:
        latest_res = requests.get(latest_url, timeout=10)
        if latest_res.status_code == 200:
            payload["latest_rate"] = latest_res.json().get("rates", {}).get("JPY", "N/A")

        history_res = requests.get(history_url, timeout=10)
        if history_res.status_code == 200:
            rates = history_res.json().get("rates", {})
            for date, rate_data in rates.items():
                payload["7_day_history"].append({
                    "date": date,
                    "rate": rate_data.get("JPY")
                })
    except Exception as e:
        payload["error"] = str(e)

    return payload

def get_road_conditions(api_key=None):
    api_key = api_key or ORS_API_KEY
    if not api_key:
        return {"error": "ORS_API_KEY not found in environment variables."}

    waypoints = [
        {"name": "New Chitose Airport", "coords": [141.6811, 42.7875]},
        {"name": "Shikotsu Mizu no Uta", "coords": [141.402, 42.774]},
        {"name": "Niseko Northern Resort", "coords": [140.630, 42.843]},
        {"name": "Grids Premium Otaru", "coords": [140.996, 43.193]},
        {"name": "Furano La Terre", "coords": [142.434, 43.408]},
        {"name": "Sapporo Susukino", "coords": [141.353, 43.055]}
    ]

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    payload = {"coordinates": [wp["coords"] for wp in waypoints], "elevation": True, "instructions": True}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            return {"error": f"API Status {response.status_code}", "details": response.text}

        route = response.json()["routes"][0]
        summary = route["summary"]
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

def get_daily_commutes(api_key=None):
    """Calculates daily drive times between basecamps and target ski resorts and towns."""
    api_key = api_key or ORS_API_KEY
    if not api_key:
        return {"error": "ORS_API_KEY not found."}

    commutes = [
        ({"name": "Niseko Northern Resort", "coords": [140.630, 42.843]}, {"name": "Niseko Moiwa", "coords": [140.63, 42.84]}),
        ({"name": "Niseko Northern Resort", "coords": [140.630, 42.843]}, {"name": "Rusutsu Resort", "coords": [140.90, 42.75]}),
        ({"name": "Grids Premium Otaru", "coords": [140.996, 43.193]}, {"name": "Kiroro Snow World", "coords": [140.99, 43.07]}),
        ({"name": "Furano La Terre", "coords": [142.434, 43.408]}, {"name": "Kamui Ski Links", "coords": [142.25, 43.83]}),
        ({"name": "Furano La Terre", "coords": [142.434, 43.408]}, {"name": "Furano Ski Resort", "coords": [142.33, 43.33]}),
        ({"name": "Furano La Terre", "coords": [142.434, 43.408]}, {"name": "Asahikawa Town", "coords": [142.36, 43.76]}),
        ({"name": "Sapporo Susukino", "coords": [141.353, 43.055]}, {"name": "Sapporo Teine", "coords": [141.19, 43.10]}),
        ({"name": "Sapporo Susukino", "coords": [141.353, 43.055]}, {"name": "Sapporo Kokusai", "coords": [141.07, 43.07]})
    ]

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    results = []

    for start, end in commutes:
        payload = {"coordinates": [start["coords"], end["coords"]], "elevation": False}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                route = response.json()["routes"][0]["summary"]
                results.append({
                    "from": start["name"],
                    "to": end["name"],
                    "distance_km": round(route["distance"] / 1000, 1),
                    "duration_mins": round(route["duration"] / 60)
                })
        except Exception as e:
            continue

    return results

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
        return "Daily resort news is currently unavailable."
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

    print("Fetching road conditions and daily commutes...")
    roads = get_road_conditions()
    commutes = get_daily_commutes()

    print("Fetching airport status...")
    airport = get_cts_disruptions()

    print("Fetching resort news and lift status...")
    news = get_resort_news()
    lifts = get_lift_status()

    print("Fetching official JMA weather warnings...")
    jma_warnings = get_jma_warnings()

    print("Fetching JMA earthquake data...")
    earthquakes = get_jma_earthquakes()

    print("Fetching JR Hokkaido status...")
    trains = get_jr_hokkaido_status()

    final_payload = {
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
        "currency": {
            "CAD_to_JPY": jpy_rate
        },
        "logistics": {
            "cts_airport_notices": airport,
            "jr_hokkaido_trains": trains,
            "road_trip_status": roads,
            "daily_commutes": commutes
        },
        "mountain_safety": {
            "official_jma_warnings": jma_warnings,
            "latest_earthquakes": earthquakes,
            "niseko_avalanche_bulletin": safety,
            "latest_resort_news": news
        },
        "resorts": weather,
        "lift_status": lifts,
        "onsens": ONSENS
    }

    os.makedirs('public', exist_ok=True)
    with open('public/data.json', 'w', encoding='utf-8') as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)

    print("Payload successfully generated at public/data.json")

if __name__ == "__main__":
    build_payload()
