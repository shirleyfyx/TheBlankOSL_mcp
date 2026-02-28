from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# Common US cities for location-based forecast (no external geocoding)
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "san francisco": (37.7749, -122.4194),
    "sf": (37.7749, -122.4194),
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "la": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "seattle": (47.6062, -122.3321),
    "boston": (42.3601, -71.0589),
    "denver": (39.7392, -104.9903),
    "miami": (25.7617, -80.1918),
    "austin": (30.2672, -97.7431),
    "portland": (45.5152, -122.6784),
    "phoenix": (33.4484, -112.0740),
    "dallas": (32.7767, -96.7970),
    "houston": (29.7604, -95.3698),
    "washington": (38.9072, -77.0369),
    "dc": (38.9072, -77.0369),
}

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

async def _get_forecast_impl(latitude: float, longitude: float) -> str:
    """Shared implementation for forecast by coordinates."""
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location by latitude and longitude.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    return await _get_forecast_impl(latitude, longitude)


@mcp.tool()
async def get_forecast_for_city(location: str) -> str:
    """Get weather forecast for a city or location by name.

    Use this when the user asks for weather in a city (e.g. San Francisco, NYC).
    Supports common US city names. For other locations use get_forecast with latitude/longitude.

    Args:
        location: City or location name (e.g. San Francisco, New York, Seattle)
    """
    key = (location or "").strip().lower()
    if not key:
        return "Please provide a city or location name (e.g. San Francisco)."
    coords = CITY_COORDINATES.get(key)
    if not coords:
        # Try partial match
        for city, coord in CITY_COORDINATES.items():
            if key in city or city in key:
                coords = coord
                break
    if not coords:
        return f"Unknown location '{location}'. Use get_forecast(latitude, longitude) for coordinates, or try a major US city name."
    lat, lon = coords
    return await _get_forecast_impl(lat, lon)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
