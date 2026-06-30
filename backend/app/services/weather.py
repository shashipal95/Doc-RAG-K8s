from typing import Any, Dict, Optional

import httpx


async def get_location_from_ip(ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Get latitude and longitude based on a public IP.
    If 'ip' is provided, it fetches geolocation for that specific IP.
    Otherwise, it fetches for the server's public IP.
    """
    url = f"http://ip-api.com/json/{ip}" if ip else "http://ip-api.com/json/"
    print(f"[weather] Fetching location for IP: {ip if ip else 'server-ip'}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"[weather] Location detected: {data.get('city')}, {data.get('country')}")
                return {
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "city": data.get("city"),
                    "country": data.get("country")
                }
    except Exception as e:
        print(f"Error fetching location for IP {ip}: {e}")
    return {"lat": 0, "lon": 0, "city": "Unknown", "country": "Unknown"}

async def get_weather_data(lat: float, lon: float, city_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch weather data from wttr.in in JSON format.
    """
    try:
        async with httpx.AsyncClient() as client:
            # wttr.in format=j1 returns a detailed JSON
            response = await client.get(f"https://wttr.in/{lat},{lon}?format=j1", timeout=15)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current_condition", [{}])[0]
                weather = data.get("weather", [{}])[0]
                nearest = data.get("nearest_area", [{}])[0]
                astronomy = weather.get("astronomy", [{}])[0]
                
                area_name = nearest.get("areaName", [{}])[0].get("value", "Unknown")
                country_name = nearest.get("country", [{}])[0].get("value", "")
                
                # If wttr.in returns a neighboring city (common with weather stations), 
                # but we have a reliable hint (from GPS/IP), prioritize the hint.
                final_city = area_name
                if city_hint and city_hint.lower() != "unknown":
                    # If the returned area is different but we have a hint, we use the hint
                    # (Most users would rather see "Indore" than "Ujjain" if they are in Indore outskirts)
                    final_city = city_hint

                return {
                    "temp_c": current.get("temp_C"),
                    "humidity": current.get("humidity"),
                    "wind_speed_kmh": current.get("windspeedKmph"),
                    "condition": current.get("weatherDesc", [{}])[0].get("value"),
                    "chance_of_rain": weather.get("hourly", [{}])[0].get("chanceofrain"),
                    "precip_mm": current.get("precipMM"),
                    "location_name": f"{final_city}, {country_name}".strip(", "),
                    "sunrise": astronomy.get("sunrise"),
                    "sunset": astronomy.get("sunset"),
                    "observation_time": current.get("observation_time"),
                    "weather_icon_url": current.get("weatherIconUrl", [{}])[0].get("value")
                }
    except Exception as e:
        print(f"Error fetching weather: {e}")
    return {"error": "Could not fetch weather data"}
