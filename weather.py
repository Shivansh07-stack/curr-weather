import httpx

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

