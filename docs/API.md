# Weather API Documentation

## Overview

The Weather API Aggregation System provides a unified REST API for accessing weather data collected from multiple sources. All data is aggregated, quality-scored, and served through consistent endpoints.

## Base URL

```
https://your-api-id.execute-api.{region}.amazonaws.com/{stage}
```

- **Region**: AWS region where the API is deployed (e.g., `us-east-1`)
- **Stage**: Deployment stage (`dev`, `staging`, or `prod`)

## Authentication

Currently, the API is open and does not require authentication. Future versions may include API key authentication.

## Rate Limiting

- **Burst limit**: 100 requests
- **Rate limit**: 50 requests per second
- **Monthly quota**: Unlimited (subject to AWS costs)

## Common Headers

### Request Headers

```http
Content-Type: application/json
Accept: application/json
```

### Response Headers

```http
Content-Type: application/json
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
X-Request-Id: {unique-request-id}
```

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": "Error type",
  "message": "Detailed error message",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | Resource not found |
| 429 | Too many requests (rate limited) |
| 500 | Internal server error |
| 503 | Service unavailable |

## Endpoints

### 1. Health Check

Check the health status of the API and its dependencies.

**Endpoint:** `GET /health`

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00Z",
  "location": "lewisville-tx",
  "database": {
    "status": "connected",
    "table": "weather-aggregator-prod-weather-data"
  },
  "data": {
    "last_update": "2024-01-15T11:50:00Z",
    "is_fresh": true
  },
  "version": "1.0.0"
}
```

**Status Values:**
- `healthy`: All systems operational, data is fresh
- `degraded`: System operational but data may be stale
- `unhealthy`: System errors detected

### 2. Current Weather

Get the most recent weather data.

**Endpoint:** `GET /weather/current`

**Response:**

```json
{
  "location": "lewisville-tx",
  "timestamp": "2024-01-15T12:00:00Z",
  "data_quality_score": 0.85,
  "sources": ["openweathermap", "weatherapi", "openmeteo", "visualcrossing", "tomorrow_io"],
  "current_conditions": {
    "temperature": {
      "value": 25.5,
      "min": 24.0,
      "max": 27.0,
      "unit": "celsius"
    },
    "feels_like": {
      "value": 26.0,
      "min": 25.0,
      "max": 27.5,
      "unit": "celsius"
    },
    "humidity": {
      "value": 65,
      "min": 60,
      "max": 70,
      "unit": "percent"
    },
    "pressure": {
      "value": 1013,
      "min": 1012,
      "max": 1014,
      "unit": "hPa"
    },
    "wind": {
      "speed": {
        "value": 3.5,
        "min": 3.0,
        "max": 4.0,
        "unit": "m/s"
      },
      "direction": {
        "value": 180,
        "unit": "degrees"
      }
    },
    "clouds": {
      "value": 40,
      "min": 30,
      "max": 50,
      "unit": "percent"
    },
    "visibility": {
      "value": 10000,
      "min": 9000,
      "max": 10000,
      "unit": "meters"
    },
    "uv_index": {
      "value": 5,
      "min": 4,
      "max": 6
    },
    "weather": "Partly cloudy"
  }
}
```

**Field Descriptions:**
- `data_quality_score`: Quality metric from 0-1 based on data completeness
- `sources`: List of APIs that provided data for this reading
- `value`: Average/consensus value from all sources
- `min/max`: Minimum and maximum values across sources

### 3. Historical Weather

Get historical weather data for a specified time period.

**Endpoint:** `GET /weather/history`

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| hours | integer | No | 24 | Number of hours of history (max: 168) |

**Example Request:**
```
GET /weather/history?hours=48
```

**Response:**

```json
{
  "location": "lewisville-tx",
  "period": {
    "start": "2024-01-13T12:00:00Z",
    "end": "2024-01-15T12:00:00Z",
    "hours": 48
  },
  "data_points": 144,
  "statistics": {
    "temperature": {
      "avg": 23.5,
      "min": 18.0,
      "max": 28.0
    },
    "humidity": {
      "avg": 68,
      "min": 55,
      "max": 85
    },
    "pressure": {
      "avg": 1013,
      "min": 1010,
      "max": 1016
    }
  },
  "history": [
    {
      "timestamp": "2024-01-15T12:00:00Z",
      "data_quality_score": 0.85,
      "temperature": 25.5,
      "humidity": 65,
      "pressure": 1013,
      "wind_speed": 3.5,
      "clouds": 40,
      "weather": "Partly cloudy",
      "sources_count": 5
    },
    {
      "timestamp": "2024-01-15T11:40:00Z",
      "data_quality_score": 0.80,
      "temperature": 25.2,
      "humidity": 66,
      "pressure": 1013,
      "wind_speed": 3.3,
      "clouds": 45,
      "weather": "Partly cloudy",
      "sources_count": 4
    }
  ]
}
```

### 4. Data Sources

Get information about available weather data sources.

**Endpoint:** `GET /weather/sources`

**Response:**

```json
{
  "location": "lewisville-tx",
  "coordinates": {
    "latitude": 33.0462,
    "longitude": -96.9942
  },
  "available_sources": [
    {
      "name": "OpenWeatherMap",
      "id": "openweathermap",
      "description": "Current weather, temperature, humidity, pressure, wind",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "1000 calls/day"
    },
    {
      "name": "WeatherAPI",
      "id": "weatherapi",
      "description": "Current conditions, air quality, astronomy data",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "1 million calls/month"
    },
    {
      "name": "Visual Crossing",
      "id": "visualcrossing",
      "description": "Detailed weather data, forecasts",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "1000 records/day"
    },
    {
      "name": "Open-Meteo",
      "id": "openmeteo",
      "description": "Weather forecasts, historical data",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "Unlimited (no API key required)"
    },
    {
      "name": "Tomorrow.io",
      "id": "tomorrow_io",
      "description": "Real-time weather, air quality",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "500 calls/day"
    }
  ],
  "aggregation_method": "Average values from all available sources with consensus for weather conditions",
  "update_schedule": "Every 20 minutes",
  "data_retention": "30 days"
}
```

## Data Aggregation

### Methodology

The system aggregates data from multiple sources using the following approach:

1. **Numeric Values**: Calculate average, minimum, and maximum across all sources
2. **Weather Conditions**: Use consensus (most common description)
3. **Quality Scoring**: Rate data completeness and consistency

### Quality Score Calculation

The data quality score (0-1) is calculated based on:
- Number of sources providing data
- Completeness of data fields
- Consistency between sources
- Data freshness

### Handling Missing Data

When some APIs fail or return incomplete data:
- System continues with available sources
- Quality score reflects reduced data availability
- Minimum 1 source required for valid response

## Examples

### cURL Examples

```bash
# Get current weather
curl -X GET https://api.example.com/prod/weather/current

# Get 24-hour history
curl -X GET https://api.example.com/prod/weather/history?hours=24

# Check API health
curl -X GET https://api.example.com/prod/health

# Get data sources info
curl -X GET https://api.example.com/prod/weather/sources
```

### JavaScript/Fetch

```javascript
// Get current weather
fetch('https://api.example.com/prod/weather/current')
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));

// Get historical data with parameters
const params = new URLSearchParams({ hours: 48 });
fetch(`https://api.example.com/prod/weather/history?${params}`)
  .then(response => response.json())
  .then(data => console.log(data));
```

### Python

```python
import requests

# Get current weather
response = requests.get('https://api.example.com/prod/weather/current')
data = response.json()
print(f"Temperature: {data['current_conditions']['temperature']['value']}°C")

# Get historical data
params = {'hours': 48}
response = requests.get('https://api.example.com/prod/weather/history', params=params)
history = response.json()
print(f"Data points: {history['data_points']}")
```

## Webhooks (Future Feature)

Future versions may support webhooks for:
- Severe weather alerts
- Data quality degradation
- System status changes

## Rate Limiting Best Practices

1. **Cache responses** when possible
2. **Use appropriate polling intervals** (recommended: 5+ minutes)
3. **Handle 429 responses** with exponential backoff
4. **Monitor your usage** via CloudWatch metrics

## Support

For API issues or questions:
1. Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Review CloudWatch logs for detailed error messages
3. Open an issue on GitHub

## Changelog

### Version 1.0.0 (Current)
- Initial release
- Support for 5 weather data sources
- Current and historical weather endpoints
- Data quality scoring
- Automatic aggregation

### Planned Features
- Forecast endpoints
- Weather alerts
- Custom location support
- API key authentication
- Webhook support
- GraphQL API
