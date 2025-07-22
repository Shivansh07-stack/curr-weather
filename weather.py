import httpx
import os
#from dotenv import load_dotenv

#load_dotenv()

API_KEY = os.getenv("57b9ed22b982f308139bffa1d2f3ca80")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

async def get_weather_by_city(city: str):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(BASE_URL, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json()}
