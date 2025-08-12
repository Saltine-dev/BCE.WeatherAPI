"""
Weather Data Collector Lambda Function
Fetches weather data from multiple free APIs and stores in DynamoDB
"""

import os
import json
import logging
import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from decimal import Decimal
import time
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS region configuration
REGION = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=REGION)
secrets_client = boto3.client('secretsmanager', region_name=REGION)

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'weather-data')
SECRET_ARN = os.environ.get('SECRET_MANAGER_ARN')
LOCATION = os.environ.get('LOCATION', 'lewisville-tx')
LATITUDE = float(os.environ.get('LATITUDE', '33.0462'))
LONGITUDE = float(os.environ.get('LONGITUDE', '-96.9942'))

# Resilient HTTP session for degraded connectivity
_retry_strategy = Retry(
    total=2,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_http_adapter = HTTPAdapter(max_retries=_retry_strategy)
HTTP = requests.Session()
HTTP.mount("https://", _http_adapter)
HTTP.mount("http://", _http_adapter)

class WeatherAPIClient:
    """Base class for weather API clients"""
    
    def __init__(self, api_name: str, api_key: Optional[str] = None):
        self.api_name = api_name
        self.api_key = api_key
        
    def fetch_data(self) -> Optional[Dict]:
        """Fetch weather data from the API"""
        raise NotImplementedError

class OpenWeatherMapClient(WeatherAPIClient):
    """OpenWeatherMap API client"""
    
    def fetch_data(self) -> Optional[Dict]:
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": LATITUDE,
                "lon": LONGITUDE,
                "appid": self.api_key,
                "units": "metric"
            }
            
            response = HTTP.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                "source": "openweathermap",
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data["wind"]["speed"],
                "wind_direction": data["wind"].get("deg"),
                "clouds": data["clouds"]["all"],
                "weather": data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "visibility": data.get("visibility"),
                "timestamp": data["dt"]
            }
        except Exception as e:
            logger.error(f"Error fetching OpenWeatherMap data: {str(e)}")
            return None

class WeatherAPIComClient(WeatherAPIClient):
    """WeatherAPI.com client"""
    
    def fetch_data(self) -> Optional[Dict]:
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                "key": self.api_key,
                "q": f"{LATITUDE},{LONGITUDE}",
                "aqi": "yes"
            }
            
            response = HTTP.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data["current"]
            return {
                "source": "weatherapi",
                "temperature": current["temp_c"],
                "feels_like": current["feelslike_c"],
                "humidity": current["humidity"],
                "pressure": current["pressure_mb"],
                "wind_speed": current["wind_kph"] / 3.6,  # Convert to m/s
                "wind_direction": current["wind_degree"],
                "clouds": current["cloud"],
                "weather": current["condition"]["text"],
                "description": current["condition"]["text"],
                "visibility": current["vis_km"] * 1000,  # Convert to meters
                "uv_index": current["uv"],
                "air_quality": current.get("air_quality", {})
            }
        except Exception as e:
            logger.error(f"Error fetching WeatherAPI data: {str(e)}")
            return None

class VisualCrossingClient(WeatherAPIClient):
    """Visual Crossing Weather API client"""
    
    def fetch_data(self) -> Optional[Dict]:
        try:
            url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{LATITUDE},{LONGITUDE}/today"
            params = {
                "key": self.api_key,
                "unitGroup": "metric",
                "include": "current"
            }
            
            response = HTTP.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("currentConditions", data["days"][0])
            return {
                "source": "visualcrossing",
                "temperature": current.get("temp"),
                "feels_like": current.get("feelslike"),
                "humidity": current.get("humidity"),
                "pressure": current.get("pressure"),
                "wind_speed": current.get("windspeed", 0) * 0.27778,  # km/h to m/s
                "wind_direction": current.get("winddir"),
                "clouds": current.get("cloudcover"),
                "weather": current.get("conditions"),
                "description": current.get("conditions"),
                "visibility": current.get("visibility", 0) * 1000,  # km to meters
                "uv_index": current.get("uvindex"),
                "solar_radiation": current.get("solarradiation")
            }
        except Exception as e:
            logger.error(f"Error fetching Visual Crossing data: {str(e)}")
            return None

class OpenMeteoClient(WeatherAPIClient):
    """Open-Meteo API client (no API key required)"""
    
    def fetch_data(self) -> Optional[Dict]:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m,cloud_cover",
                "timezone": "America/Chicago"
            }
            
            response = HTTP.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data["current"]
            
            # Weather code mapping
            weather_codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
                55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
                96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
            }
            
            weather_code = current.get("weather_code", 0)
            weather_desc = weather_codes.get(weather_code, "Unknown")
            
            return {
                "source": "openmeteo",
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "pressure": current.get("pressure_msl"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_direction": current.get("wind_direction_10m"),
                "clouds": current.get("cloud_cover"),
                "weather": weather_desc,
                "description": weather_desc,
                "precipitation": current.get("precipitation"),
                "weather_code": weather_code
            }
        except Exception as e:
            logger.error(f"Error fetching Open-Meteo data: {str(e)}")
            return None

class TomorrowIOClient(WeatherAPIClient):
    """Tomorrow.io API client"""
    
    def fetch_data(self) -> Optional[Dict]:
        try:
            url = "https://api.tomorrow.io/v4/weather/realtime"
            params = {
                "location": f"{LATITUDE},{LONGITUDE}",
                "apikey": self.api_key,
                "units": "metric"
            }
            
            response = HTTP.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            values = data["data"]["values"]
            
            # Weather code to description mapping
            weather_codes = {
                1000: "Clear", 1100: "Mostly Clear", 1101: "Partly Cloudy",
                1102: "Mostly Cloudy", 1001: "Cloudy", 2000: "Fog",
                4000: "Drizzle", 4001: "Rain", 4200: "Light Rain",
                4201: "Heavy Rain", 5000: "Snow", 5001: "Flurries",
                5100: "Light Snow", 5101: "Heavy Snow", 6000: "Freezing Drizzle",
                6001: "Freezing Rain", 6200: "Light Freezing Rain",
                6201: "Heavy Freezing Rain", 7000: "Ice Pellets",
                7101: "Heavy Ice Pellets", 7102: "Light Ice Pellets",
                8000: "Thunderstorm"
            }
            
            weather_code = values.get("weatherCode", 1000)
            weather_desc = weather_codes.get(weather_code, "Unknown")
            
            return {
                "source": "tomorrow_io",
                "temperature": values.get("temperature"),
                "feels_like": values.get("temperatureApparent"),
                "humidity": values.get("humidity"),
                "pressure": values.get("pressureSurfaceLevel"),
                "wind_speed": values.get("windSpeed"),
                "wind_direction": values.get("windDirection"),
                "clouds": values.get("cloudCover"),
                "weather": weather_desc,
                "description": weather_desc,
                "visibility": values.get("visibility"),
                "uv_index": values.get("uvIndex"),
                "precipitation_intensity": values.get("precipitationIntensity")
            }
        except Exception as e:
            logger.error(f"Error fetching Tomorrow.io data: {str(e)}")
            return None

def get_api_keys() -> Dict[str, str]:
    """Retrieve API keys from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
        return json.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Error retrieving secrets: {str(e)}")
        return {}

def decimal_default(obj):
    """JSON encoder for Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def calculate_data_quality_score(data_points: List[Dict]) -> float:
    """Calculate data quality score based on available data points"""
    if not data_points:
        return 0.0
    
    total_score = 0
    for point in data_points:
        if point:
            # Count non-None values
            valid_fields = sum(1 for v in point.values() if v is not None)
            total_fields = len(point)
            total_score += (valid_fields / total_fields)
    
    return round(total_score / len(data_points), 2)

def aggregate_weather_data(data_points: List[Dict]) -> Dict:
    """Aggregate weather data from multiple sources"""
    if not data_points:
        return {}
    
    # Filter out None values
    valid_data = [d for d in data_points if d is not None]
    if not valid_data:
        return {}
    
    aggregated = {
        "temperature": [],
        "feels_like": [],
        "humidity": [],
        "pressure": [],
        "wind_speed": [],
        "wind_direction": [],
        "clouds": [],
        "visibility": [],
        "uv_index": [],
        "sources": []
    }
    
    # Collect all values
    for data in valid_data:
        aggregated["sources"].append(data.get("source"))
        for field in ["temperature", "feels_like", "humidity", "pressure", 
                     "wind_speed", "wind_direction", "clouds", "visibility", "uv_index"]:
            value = data.get(field)
            if value is not None:
                aggregated[field].append(value)
    
    # Calculate averages and consensus
    result = {
        "sources": aggregated["sources"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_data": valid_data
    }
    
    # Calculate averages for numeric fields (handle single-source gracefully)
    for field in ["temperature", "feels_like", "humidity", "pressure", 
                 "wind_speed", "wind_direction", "clouds", "visibility", "uv_index"]:
        if aggregated[field]:
            result[f"{field}_avg"] = round(sum(aggregated[field]) / len(aggregated[field]), 2)
            result[f"{field}_min"] = round(min(aggregated[field]), 2)
            result[f"{field}_max"] = round(max(aggregated[field]), 2)
            result[f"{field}_count"] = len(aggregated[field])
    
    # Get most common weather description
    weather_descriptions = [d.get("weather") for d in valid_data if d.get("weather")]
    if weather_descriptions:
        from collections import Counter
        result["weather_consensus"] = Counter(weather_descriptions).most_common(1)[0][0]
    
    return result

def convert_to_dynamodb_format(data: Dict) -> Dict:
    """Convert data to DynamoDB-compatible format"""
    def convert_value(value):
        if isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [convert_value(item) for item in value]
        return value
    
    return convert_value(data)

def store_in_dynamodb(weather_data: Dict, quality_score: float):
    """Store aggregated weather data in DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Calculate TTL (30 days from now)
        ttl = int(time.time()) + (30 * 24 * 60 * 60)
        
        item = {
            "location": LOCATION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weather_data": convert_to_dynamodb_format(weather_data),
            "data_quality_score": Decimal(str(quality_score)),
            "ttl": ttl
        }
        
        table.put_item(Item=item)
        logger.info(f"Successfully stored weather data for {LOCATION}")
        
    except Exception as e:
        logger.error(f"Error storing data in DynamoDB: {str(e)}")
        raise

def lambda_handler(event, context):
    """Main Lambda handler function"""
    logger.info(f"Weather collector started for location: {LOCATION}")
    
    try:
        # Get API keys
        api_keys = get_api_keys()
        
        # Initialize API clients
        clients = []
        
        if api_keys.get("openweathermap"):
            clients.append(OpenWeatherMapClient("openweathermap", api_keys["openweathermap"]))
        
        if api_keys.get("weatherapi"):
            clients.append(WeatherAPIComClient("weatherapi", api_keys["weatherapi"]))
        
        if api_keys.get("visualcrossing"):
            clients.append(VisualCrossingClient("visualcrossing", api_keys["visualcrossing"]))
        
        # Open-Meteo doesn't require an API key
        clients.append(OpenMeteoClient("openmeteo"))
        
        if api_keys.get("tomorrow_io"):
            clients.append(TomorrowIOClient("tomorrow_io", api_keys["tomorrow_io"]))
        
        # Fetch data from all APIs
        all_data = []
        for client in clients:
            logger.info(f"Fetching data from {client.api_name}")
            data = client.fetch_data()
            if data:
                all_data.append(data)
                logger.info(f"Successfully fetched data from {client.api_name}")
        
        if not all_data:
            raise Exception("No weather data could be fetched from any API")
        
        # Aggregate the data
        aggregated_data = aggregate_weather_data(all_data)
        
        # Calculate data quality score
        quality_score = calculate_data_quality_score(all_data)
        
        # Store in DynamoDB
        store_in_dynamodb(aggregated_data, quality_score)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Weather data collected successfully",
                "location": LOCATION,
                "sources_count": len(all_data),
                "quality_score": quality_score,
                "timestamp": aggregated_data["timestamp"]
            }, default=decimal_default)
        }
        
    except Exception as e:
        logger.error(f"Error in weather collector: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to collect weather data",
                "message": str(e)
            })
        }
