import os
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
from dotenv import load_dotenv
load_dotenv()
import uvicorn

app = FastAPI(title = "Weather API")

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"


async def fetch(url: str, params: dict):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        return response.json()
    
@app.get("/weather/pollution/{city}")
async def air_pollution(city: str):
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    # Get coordinates from city name
    geo_params = {"q": city, "limit": 1, "appid": API_KEY}
    
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEO_URL, params=geo_params)
        geo_data = geo_resp.json()
        if not geo_data or not isinstance(geo_data, list) or len(geo_data) == 0:
            return {"error": "City not found"}
        
        
        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        if lat is None or lon is None:
            return {"error": "Coordinates not found for city"}
        
        
        # Query air pollution API
        pollution_params = {"lat": lat, "lon": lon, "appid": API_KEY}
        pollution_resp = await client.get(f"{BASE_URL}air_pollution", params=pollution_params)
        pollution_data = pollution_resp.json()
        # Extract components
        
        
        try:
            components = pollution_data["list"][0]["components"]
            print("Components data:", components)  # Print to console

            # Extract values
            so2 = components.get("so2")
            no2 = components.get("no2")
            pm10 = components.get("pm10")
            pm25 = components.get("pm2_5")
            o3 = components.get("o3")
            co = components.get("co")

            def get_index_and_name(so2, no2, pm10, pm25, o3, co):
                # Helper to get index for each pollutant
                def get_idx(val, ranges):
                    for idx, (low, high) in enumerate(ranges, 1):
                        if low <= val < high:
                            return idx
                    return len(ranges) + 1

                so2_idx = get_idx(so2, [(0,20),(20,80),(80,250),(250,350),(350,float('inf'))])
                no2_idx = get_idx(no2, [(0,40),(40,70),(70,150),(150,200),(200,float('inf'))])
                pm10_idx = get_idx(pm10, [(0,20),(20,50),(50,100),(100,200),(200,float('inf'))])
                pm25_idx = get_idx(pm25, [(0,10),(10,25),(25,50),(50,75),(75,float('inf'))])
                o3_idx = get_idx(o3, [(0,60),(60,100),(100,140),(140,180),(180,float('inf'))])
                co_idx = get_idx(co, [(0,4400),(4400,9400),(9400,12400),(12400,15400),(15400,float('inf'))])

                # Take the worst index as overall
                indices = [so2_idx, no2_idx, pm10_idx, pm25_idx, o3_idx, co_idx]
                overall_idx = max(indices)
                qualitative_names = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
                overall_name = qualitative_names[overall_idx-1] if 1 <= overall_idx <= 5 else "Unknown"

                return overall_idx, overall_name

            index, qualitative_name = get_index_and_name(so2, no2, pm10, pm25, o3, co)

            filtered = {
                "SO2": so2,
                "NO2": no2,
                "PM10": pm10,
                "PM2.5": pm25,
                "O3": o3,
                "CO": co,
                "Index": index,
                "Qualitative Name": qualitative_name
            }
            return filtered
        except (KeyError, IndexError):
            return {"error": "Components data not found in response"}
    
@app.get("/weather/current/{city}")
async def current_weather(city: str):
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    # Get coordinates from city name
    geo_params = {"q": city, "limit": 1, "appid": API_KEY}
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEO_URL, params=geo_params)
        geo_data = geo_resp.json()
        if not geo_data or not isinstance(geo_data, list) or len(geo_data) == 0:
            return {"error": "City not found"}
        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        if lat is None or lon is None:
            return {"error": "Coordinates not found for city"}
        # Query current weather API
        weather_params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric"}
        weather_resp = await client.get(f"{BASE_URL}weather", params=weather_params)
        weather_data = weather_resp.json()
        try:
            result = {
                "city": city,
                "temperature": weather_data["main"]["temp"],
                "description": weather_data["weather"][0]["description"],
                "humidity": weather_data["main"]["humidity"],
                "pressure": weather_data["main"]["pressure"],
                "wind_speed": weather_data["wind"]["speed"]
            }
            return result
        except (KeyError, IndexError):
            return {"error": "Weather data not found in response"}
    
@app.get("/weather/forecast/{city}")
async def short_term_forecast(city: str, days: int = 3):
    """
    Fetch short-term weather forecast data for planning (3-7 days) using 3-hourly forecast.
    """
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    if days < 3 or days > 7:
        return {"error": "Days parameter must be between 3 and 7."}
    geo_params = {"q": city, "limit": 1, "appid": API_KEY}
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEO_URL, params=geo_params)
        geo_data = geo_resp.json()
        if not geo_data or not isinstance(geo_data, list) or len(geo_data) == 0:
            return {"error": "City not found"}
        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        if lat is None or lon is None:
            return {"error": "Coordinates not found for city"}
        # Query 3-hourly forecast API
        forecast_params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": "metric"
        }
        forecast_resp = await client.get(f"{BASE_URL}forecast", params=forecast_params)
        forecast_data = forecast_resp.json()
        try:
            from collections import defaultdict
            import datetime

            daily_data = defaultdict(list)
            for entry in forecast_data.get("list", []):
                dt = datetime.datetime.utcfromtimestamp(entry["dt"])
                day = dt.date()
                daily_data[day].append(entry)

            # Prepare daily summaries for requested days
            forecast_list = []
            for i, (day, entries) in enumerate(daily_data.items()):
                if i >= days:
                    break
                temps = [e["main"]["temp"] for e in entries]
                descriptions = [e["weather"][0]["description"] for e in entries]
                summary = {
                    "date": str(day),
                    "avg_temp": round(sum(temps)/len(temps), 2) if temps else None,
                    "main_description": max(set(descriptions), key=descriptions.count) if descriptions else None
                }
                forecast_list.append(summary)

            return {
                "city": city,
                "days": days,
                "forecast": forecast_list
            }
        except Exception:
            return {"error": "Forecast data not found in response"}
    


@app.get("/weather/current/by-coords")
async def weather_by_coords(lat: float, lon: float):
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    weather_params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric"}
    async with httpx.AsyncClient() as client:
        weather_resp = await client.get(f"{BASE_URL}weather", params=weather_params)
        weather_data = weather_resp.json()
        try:
            result = {
                "latitude": lat,
                "longitude": lon,
                "temperature": weather_data["main"]["temp"],
                "description": weather_data["weather"][0]["description"],
                "humidity": weather_data["main"]["humidity"],
                "pressure": weather_data["main"]["pressure"],
                "wind_speed": weather_data["wind"]["speed"]
            }
            return result
        except (KeyError, IndexError):
            return {"error": "Weather data not found in response"}

@app.get("/weather/current/by-ip")
async def weather_by_ip(request: Request):
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    # Automatically get user's IP from request headers or fallback to client.host
    client_ip = request.headers.get("x-forwarded-for", request.client.host)
    # If multiple IPs are present, take the first one
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(f"https://ipinfo.io/{client_ip}/json")
        loc = geo_resp.json().get("loc", "")
        if loc:
            lat, lon = map(float, loc.split(","))
            weather_params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric"}
            weather_resp = await client.get(f"{BASE_URL}weather", params=weather_params)
            weather_data = weather_resp.json()
            print("Weather data:", weather_data)  # Debug print
            if weather_data.get("cod") != 200:
                return {"error": weather_data.get("message", "Weather data not found for coordinates")}
            try:
                result = {
                    "ip": client_ip,
                    "latitude": lat,
                    "longitude": lon,
                    "temperature": weather_data["main"]["temp"],
                    "description": weather_data["weather"][0]["description"],
                    "humidity": weather_data["main"]["humidity"],
                    "pressure": weather_data["main"]["pressure"],
                    "wind_speed": weather_data["wind"]["speed"]
                }
                return result
            except (KeyError, IndexError):
                return {"error": "Weather data not found in response"}
        else:
            return {"error": "IP geolocation failed."}

@app.get("/weather/forecast/hourly/{city}")
async def hourly_forecast(city: str, hours: int = 24):
    """
    Fetch 24–48 hours forecast in 3-hour blocks for a given city using the free /forecast endpoint.
    """
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    if hours < 1 or hours > 48:
        return {"error": "Hours parameter must be between 1 and 48."}
    geo_params = {"q": city, "limit": 1, "appid": API_KEY}
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEO_URL, params=geo_params)
        geo_data = geo_resp.json()
        if not geo_data or not isinstance(geo_data, list) or len(geo_data) == 0:
            return {"error": "City not found"}
        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        if lat is None or lon is None:
            return {"error": "Coordinates not found for city"}
        # Query /forecast API for 3-hourly forecast
        forecast_params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": "metric"
        }
        forecast_resp = await client.get(f"{BASE_URL}forecast", params=forecast_params)
        forecast_data = forecast_resp.json()
        try:
            forecast_list = forecast_data.get("list", [])[:hours]  # Each entry is a 3-hour block
            formatted = []
            from datetime import datetime
            for entry in forecast_list:
                formatted.append({
                    "time": datetime.utcfromtimestamp(entry["dt"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "temperature": entry["main"]["temp"],
                    "description": entry["weather"][0]["description"],
                    "humidity": entry["main"]["humidity"],
                    "pressure": entry["main"]["pressure"],
                    "wind_speed": entry["wind"]["speed"]
                })
            return {
                "city": city,
                "hours": hours,
                "forecast": formatted
            }
        except Exception:
            return {"error": "Hourly forecast data not found in response"}

@app.get("/weather/alerts/{city}")
async def weather_alerts(city: str):
    """
    Display severe weather alerts for a given city using OpenWeatherMap's One Call API.
    """
    if not API_KEY:
        return {"error": "API key not found. Please set API_KEY in your .env file."}
    # Get coordinates from city name
    geo_params = {"q": city, "limit": 1, "appid": API_KEY}
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEO_URL, params=geo_params)
        geo_data = geo_resp.json()
        if not geo_data or not isinstance(geo_data, list) or len(geo_data) == 0:
            return {"error": "City not found"}
        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        if lat is None or lon is None:
            return {"error": "Coordinates not found for city"}
        # Query One Call API for alerts
        alerts_params = {
            "lat": lat,
            "lon": lon,
            "exclude": "current,minutely,hourly,daily",
            "appid": API_KEY,
            "units": "metric"
        }
        alerts_resp = await client.get(f"{BASE_URL}onecall", params=alerts_params)
        alerts_data = alerts_resp.json()
        try:
            alerts = alerts_data.get("alerts", [])
            if not alerts:
                return {"city": city, "alerts": [], "message": "No severe weather alerts at this time."}
            # Format alerts
            formatted_alerts = []
            for alert in alerts:
                formatted_alerts.append({
                    "event": alert.get("event"),
                    "start": alert.get("start"),
                    "end": alert.get("end"),
                    "description": alert.get("description"),
                    "sender_name": alert.get("sender_name")
                })
            return {
                "city": city,
                "alerts": formatted_alerts
            }
        except Exception:
            return {"error": "Weather alerts data not found in response"}

#

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
