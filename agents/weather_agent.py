import os
import requests
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from geopy.geocoders import Nominatim

load_dotenv()

def get_city_coordinates(place_name: str):
    """Geocodes a place name to (latitude, longitude) using GeoPy directly."""
    geolocator = Nominatim(user_agent="weather_agent_app")
    try:
        location = geolocator.geocode(place_name, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

@tool
def check_weather(place: str) -> str:
    """Get the weather for a given city."""
    lat, lon = get_city_coordinates(place)
    if lat is None or lon is None:
        return f"Could not find geographic coordinates for {place}."

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": os.getenv("OPEN_WEATHER_API"),
        "units": "metric"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

    forecast_summary = []
    try:
        for item in data.get("list", [])[:3]:
            dt_txt = item.get("dt_txt")
            temp = item["main"]["temp"]
            desc = item["weather"][0]["description"]
            forecast_summary.append(f"{dt_txt}: {temp}°C, {desc.capitalize()}")
            
        return "Weather Forecast:\n" + "\n".join(forecast_summary)
    except Exception as e:
        return f"Failed to retrieve weather report. Error: {str(e)}"

def weather_agent():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.3,
    )
    tools = [check_weather]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a friendly weather report agent and your name is Dinesh."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    my_agent = create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    # Executable wrapper required for running tool loops
    return AgentExecutor(agent=my_agent, tools=tools)