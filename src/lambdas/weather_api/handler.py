"""
Weather API Lambda Function
Serves aggregated weather data through REST API endpoints
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'weather-data')
LOCATION = os.environ.get('LOCATION', 'lewisville-tx')
CORS_ORIGIN = os.environ.get('CORS_ORIGIN', '*')

class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert DynamoDB Decimal types to JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        return super(DecimalEncoder, self).default(obj)

def create_response(status_code: int, body: Any, headers: Optional[Dict] = None) -> Dict:
    """Create standardized API response"""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': CORS_ORIGIN,
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def get_current_weather() -> Dict:
    """Get the most recent weather data"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Query for the most recent data
        response = table.query(
            KeyConditionExpression=Key('location').eq(LOCATION),
            ScanIndexForward=False,  # Sort in descending order
            Limit=1
        )
        
        if not response['Items']:
            return create_response(404, {
                'error': 'No weather data found',
                'message': 'No weather data available for the specified location'
            })
        
        item = response['Items'][0]
        weather_data = item.get('weather_data', {})
        
        # Prepare response data
        current_data = {
            'location': item.get('location'),
            'timestamp': item.get('timestamp'),
            'data_quality_score': float(item.get('data_quality_score', 0)),
            'sources': weather_data.get('sources', []),
            'current_conditions': {
                'temperature': {
                    'value': weather_data.get('temperature_avg'),
                    'min': weather_data.get('temperature_min'),
                    'max': weather_data.get('temperature_max'),
                    'unit': 'celsius'
                },
                'feels_like': {
                    'value': weather_data.get('feels_like_avg'),
                    'min': weather_data.get('feels_like_min'),
                    'max': weather_data.get('feels_like_max'),
                    'unit': 'celsius'
                },
                'humidity': {
                    'value': weather_data.get('humidity_avg'),
                    'min': weather_data.get('humidity_min'),
                    'max': weather_data.get('humidity_max'),
                    'unit': 'percent'
                },
                'pressure': {
                    'value': weather_data.get('pressure_avg'),
                    'min': weather_data.get('pressure_min'),
                    'max': weather_data.get('pressure_max'),
                    'unit': 'hPa'
                },
                'wind': {
                    'speed': {
                        'value': weather_data.get('wind_speed_avg'),
                        'min': weather_data.get('wind_speed_min'),
                        'max': weather_data.get('wind_speed_max'),
                        'unit': 'm/s'
                    },
                    'direction': {
                        'value': weather_data.get('wind_direction_avg'),
                        'unit': 'degrees'
                    }
                },
                'clouds': {
                    'value': weather_data.get('clouds_avg'),
                    'min': weather_data.get('clouds_min'),
                    'max': weather_data.get('clouds_max'),
                    'unit': 'percent'
                },
                'visibility': {
                    'value': weather_data.get('visibility_avg'),
                    'min': weather_data.get('visibility_min'),
                    'max': weather_data.get('visibility_max'),
                    'unit': 'meters'
                },
                'uv_index': {
                    'value': weather_data.get('uv_index_avg'),
                    'min': weather_data.get('uv_index_min'),
                    'max': weather_data.get('uv_index_max')
                },
                'weather': weather_data.get('weather_consensus', 'Unknown')
            }
        }
        
        # Add raw data if requested
        include_raw = False  # Can be made configurable via query parameter
        if include_raw:
            current_data['raw_data'] = weather_data.get('raw_data', [])
        
        return create_response(200, current_data)
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_response(500, {
            'error': 'Database error',
            'message': 'Failed to retrieve weather data'
        })
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })

def get_historical_weather(hours: int = 24) -> Dict:
    """Get historical weather data for the specified number of hours"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Calculate the start time
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Query for historical data
        response = table.query(
            KeyConditionExpression=Key('location').eq(LOCATION) & 
                                 Key('timestamp').between(
                                     start_time.isoformat(),
                                     end_time.isoformat()
                                 ),
            ScanIndexForward=False  # Sort in descending order
        )
        
        if not response['Items']:
            return create_response(404, {
                'error': 'No historical data found',
                'message': f'No weather data available for the past {hours} hours'
            })
        
        # Process historical data
        historical_data = []
        for item in response['Items']:
            weather_data = item.get('weather_data', {})
            historical_data.append({
                'timestamp': item.get('timestamp'),
                'data_quality_score': float(item.get('data_quality_score', 0)),
                'temperature': weather_data.get('temperature_avg'),
                'humidity': weather_data.get('humidity_avg'),
                'pressure': weather_data.get('pressure_avg'),
                'wind_speed': weather_data.get('wind_speed_avg'),
                'clouds': weather_data.get('clouds_avg'),
                'weather': weather_data.get('weather_consensus'),
                'sources_count': len(weather_data.get('sources', []))
            })
        
        # Calculate statistics
        if historical_data:
            temps = [d['temperature'] for d in historical_data if d.get('temperature')]
            humidity = [d['humidity'] for d in historical_data if d.get('humidity')]
            pressure = [d['pressure'] for d in historical_data if d.get('pressure')]
            
            statistics = {
                'temperature': {
                    'avg': round(sum(temps) / len(temps), 2) if temps else None,
                    'min': min(temps) if temps else None,
                    'max': max(temps) if temps else None
                },
                'humidity': {
                    'avg': round(sum(humidity) / len(humidity), 2) if humidity else None,
                    'min': min(humidity) if humidity else None,
                    'max': max(humidity) if humidity else None
                },
                'pressure': {
                    'avg': round(sum(pressure) / len(pressure), 2) if pressure else None,
                    'min': min(pressure) if pressure else None,
                    'max': max(pressure) if pressure else None
                }
            }
        else:
            statistics = {}
        
        response_data = {
            'location': LOCATION,
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours
            },
            'data_points': len(historical_data),
            'statistics': statistics,
            'history': historical_data
        }
        
        return create_response(200, response_data)
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_response(500, {
            'error': 'Database error',
            'message': 'Failed to retrieve historical data'
        })
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })

def get_data_sources() -> Dict:
    """Get information about available data sources"""
    sources_info = {
        'location': LOCATION,
        'coordinates': {
            'latitude': 33.0462,
            'longitude': -96.9942
        },
        'available_sources': [
            {
                'name': 'OpenWeatherMap',
                'id': 'openweathermap',
                'description': 'Current weather, temperature, humidity, pressure, wind',
                'update_frequency': 'Every 20 minutes',
                'free_tier_limit': '1000 calls/day'
            },
            {
                'name': 'WeatherAPI',
                'id': 'weatherapi',
                'description': 'Current conditions, air quality, astronomy data',
                'update_frequency': 'Every 20 minutes',
                'free_tier_limit': '1 million calls/month'
            },
            {
                'name': 'Visual Crossing',
                'id': 'visualcrossing',
                'description': 'Detailed weather data, forecasts',
                'update_frequency': 'Every 20 minutes',
                'free_tier_limit': '1000 records/day'
            },
            {
                'name': 'Open-Meteo',
                'id': 'openmeteo',
                'description': 'Weather forecasts, historical data',
                'update_frequency': 'Every 20 minutes',
                'free_tier_limit': 'Unlimited (no API key required)'
            },
            {
                'name': 'Tomorrow.io',
                'id': 'tomorrow_io',
                'description': 'Real-time weather, air quality',
                'update_frequency': 'Every 20 minutes',
                'free_tier_limit': '500 calls/day'
            }
        ],
        'aggregation_method': 'Average values from all available sources with consensus for weather conditions',
        'update_schedule': 'Every 20 minutes',
        'data_retention': '30 days'
    }
    
    return create_response(200, sources_info)

def get_health_status() -> Dict:
    """Health check endpoint"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Check if we can access the table
        response = table.query(
            KeyConditionExpression=Key('location').eq(LOCATION),
            ScanIndexForward=False,
            Limit=1
        )
        
        # Check data freshness
        data_fresh = False
        last_update = None
        if response['Items']:
            last_update = response['Items'][0].get('timestamp')
            last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            time_diff = datetime.now(timezone.utc) - last_update_time
            data_fresh = time_diff.total_seconds() < 1800  # Data is fresh if less than 30 minutes old
        
        health_status = {
            'status': 'healthy' if data_fresh else 'degraded',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'location': LOCATION,
            'database': {
                'status': 'connected',
                'table': TABLE_NAME
            },
            'data': {
                'last_update': last_update,
                'is_fresh': data_fresh
            },
            'version': '1.0.0'
        }
        
        return create_response(200, health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return create_response(503, {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

def lambda_handler(event, context):
    """Main Lambda handler for API requests"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Handle OPTIONS requests for CORS
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {})
    
    # Extract path and query parameters
    path = event.get('path', '/')
    query_params = event.get('queryStringParameters', {}) or {}
    
    # Route to appropriate handler
    if path == '/weather/current':
        return get_current_weather()
    
    elif path == '/weather/history':
        hours = int(query_params.get('hours', 24))
        # Limit to maximum 7 days
        hours = min(hours, 168)
        return get_historical_weather(hours)
    
    elif path == '/weather/sources':
        return get_data_sources()
    
    elif path == '/health':
        return get_health_status()
    
    else:
        return create_response(404, {
            'error': 'Not found',
            'message': f'Path {path} not found',
            'available_endpoints': [
                '/weather/current',
                '/weather/history?hours=24',
                '/weather/sources',
                '/health'
            ]
        })
