from fastapi import FastAPI, HTTPException
from weather import get_weather_by_city

app = FastAPI(title="Live Weather API")

@app.get("/weather/{city}")
async def fetch_weather(city: str):
    data = await get_weather_by_city(city)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "description": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"]
    }
