"""
Unit tests for Weather Collector Lambda function
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

# Load weather_collector handler module with a unique name to avoid collisions
_collector_path = (
    Path(__file__).resolve().parents[2]
    / 'src' / 'lambdas' / 'weather_collector' / 'handler.py'
)
_collector_spec = importlib.util.spec_from_file_location(
    'weather_collector_handler', str(_collector_path)
)
weather_collector_handler = importlib.util.module_from_spec(_collector_spec)
assert _collector_spec and _collector_spec.loader
_collector_spec.loader.exec_module(weather_collector_handler)
# Register module so @patch can resolve it by name
import sys as _sys
_sys.modules['weather_collector_handler'] = weather_collector_handler


class TestWeatherAPIClients(unittest.TestCase):
    """Test weather API client classes"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_api_key = "test_api_key"
        
    @patch('weather_collector_handler.requests.get')
    def test_openweathermap_client_success(self, mock_get):
        """Test OpenWeatherMap client successful data fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {
                "temp": 25.5,
                "feels_like": 26.0,
                "humidity": 65,
                "pressure": 1013
            },
            "wind": {
                "speed": 3.5,
                "deg": 180
            },
            "clouds": {"all": 40},
            "weather": [{"main": "Clouds", "description": "scattered clouds"}],
            "visibility": 10000,
            "dt": 1234567890
        }
        mock_get.return_value = mock_response
        
        client = weather_collector_handler.OpenWeatherMapClient("openweathermap", self.mock_api_key)
        result = client.fetch_data()
        
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "openweathermap")
        self.assertEqual(result["temperature"], 25.5)
        self.assertEqual(result["humidity"], 65)
        
    @patch('weather_collector_handler.requests.get')
    def test_openweathermap_client_failure(self, mock_get):
        """Test OpenWeatherMap client handling API failure"""
        mock_get.side_effect = Exception("API Error")
        
        client = weather_collector_handler.OpenWeatherMapClient("openweathermap", self.mock_api_key)
        result = client.fetch_data()
        
        self.assertIsNone(result)
    
    @patch('weather_collector_handler.requests.get')
    def test_weatherapi_client_success(self, mock_get):
        """Test WeatherAPI.com client successful data fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {
                "temp_c": 24.0,
                "feelslike_c": 25.0,
                "humidity": 70,
                "pressure_mb": 1015,
                "wind_kph": 15,
                "wind_degree": 90,
                "cloud": 50,
                "condition": {"text": "Partly cloudy"},
                "vis_km": 10,
                "uv": 5,
                "air_quality": {"pm2_5": 12.5}
            }
        }
        mock_get.return_value = mock_response
        
        client = weather_collector_handler.WeatherAPIComClient("weatherapi", self.mock_api_key)
        result = client.fetch_data()
        
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "weatherapi")
        self.assertEqual(result["temperature"], 24.0)
        self.assertAlmostEqual(result["wind_speed"], 15 / 3.6, places=2)
        
    @patch('weather_collector_handler.requests.get')
    def test_openmeteo_client_success(self, mock_get):
        """Test Open-Meteo client successful data fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {
                "temperature_2m": 23.5,
                "apparent_temperature": 24.0,
                "relative_humidity_2m": 60,
                "pressure_msl": 1012,
                "wind_speed_10m": 5.0,
                "wind_direction_10m": 270,
                "cloud_cover": 30,
                "weather_code": 2,
                "precipitation": 0.0
            }
        }
        mock_get.return_value = mock_response
        
        client = weather_collector_handler.OpenMeteoClient("openmeteo")
        result = client.fetch_data()
        
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "openmeteo")
        self.assertEqual(result["temperature"], 23.5)
        self.assertEqual(result["weather"], "Partly cloudy")


class TestDataProcessing(unittest.TestCase):
    """Test data processing functions"""
    
    def test_calculate_data_quality_score(self):
        """Test data quality score calculation"""
        data_points = [
            {"temp": 25, "humidity": 65, "pressure": 1013},
            {"temp": 24, "humidity": None, "pressure": 1014},
            None,
            {"temp": 26, "humidity": 70, "pressure": 1012}
        ]
        
        score = weather_collector_handler.calculate_data_quality_score(data_points)
        
        # (3/3 + 2/3 + 0 + 3/3) / 4 = 0.67
        self.assertAlmostEqual(score, 0.67, places=2)
    
    def test_calculate_data_quality_score_empty(self):
        """Test data quality score with empty data"""
        score = weather_collector_handler.calculate_data_quality_score([])
        self.assertEqual(score, 0.0)
    
    def test_aggregate_weather_data(self):
        """Test weather data aggregation"""
        data_points = [
            {
                "source": "api1",
                "temperature": 25.0,
                "humidity": 65,
                "pressure": 1013,
                "weather": "Cloudy"
            },
            {
                "source": "api2",
                "temperature": 24.0,
                "humidity": 70,
                "pressure": 1014,
                "weather": "Cloudy"
            },
            {
                "source": "api3",
                "temperature": 26.0,
                "humidity": 60,
                "pressure": 1012,
                "weather": "Partly cloudy"
            }
        ]
        
        result = weather_collector_handler.aggregate_weather_data(data_points)
        
        self.assertEqual(len(result["sources"]), 3)
        self.assertAlmostEqual(result["temperature_avg"], 25.0, places=1)
        self.assertEqual(result["temperature_min"], 24.0)
        self.assertEqual(result["temperature_max"], 26.0)
        self.assertEqual(result["weather_consensus"], "Cloudy")
    
    def test_aggregate_weather_data_empty(self):
        """Test aggregation with empty data"""
        result = weather_collector_handler.aggregate_weather_data([])
        self.assertEqual(result, {})
    
    def test_convert_to_dynamodb_format(self):
        """Test conversion to DynamoDB format"""
        data = {
            "temperature": 25.5,
            "humidity": 65,
            "nested": {
                "value": 10.2
            },
            "list": [1.5, 2.5, 3.5]
        }
        
        result = weather_collector_handler.convert_to_dynamodb_format(data)
        
        self.assertIsInstance(result["temperature"], Decimal)
        self.assertEqual(result["temperature"], Decimal('25.5'))
        self.assertIsInstance(result["nested"]["value"], Decimal)
        self.assertIsInstance(result["list"][0], Decimal)


class TestLambdaHandler(unittest.TestCase):
    """Test main Lambda handler function"""
    
    @patch('weather_collector_handler.store_in_dynamodb')
    @patch('weather_collector_handler.get_api_keys')
    @patch('weather_collector_handler.OpenWeatherMapClient')
    @patch('weather_collector_handler.OpenMeteoClient')
    def test_lambda_handler_success(self, mock_openmeteo, mock_openweather, mock_get_keys, mock_store):
        """Test successful Lambda execution"""
        # Mock API keys
        mock_get_keys.return_value = {
            "openweathermap": "test_key"
        }
        
        # Mock weather clients
        mock_owm_instance = Mock()
        mock_owm_instance.fetch_data.return_value = {
            "source": "openweathermap",
            "temperature": 25.0,
            "humidity": 65
        }
        mock_openweather.return_value = mock_owm_instance
        
        mock_om_instance = Mock()
        mock_om_instance.fetch_data.return_value = {
            "source": "openmeteo",
            "temperature": 24.0,
            "humidity": 70
        }
        mock_openmeteo.return_value = mock_om_instance
        
        # Call handler
        result = weather_collector_handler.lambda_handler({}, {})
        
        # Verify response
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["message"], "Weather data collected successfully")
        self.assertEqual(body["sources_count"], 2)
        
        # Verify DynamoDB storage was called
        mock_store.assert_called_once()
    
    @patch('weather_collector_handler.get_api_keys')
    def test_lambda_handler_no_data(self, mock_get_keys):
        """Test Lambda handler when no data can be fetched"""
        mock_get_keys.return_value = {}
        
        result = weather_collector_handler.lambda_handler({}, {})
        
        self.assertEqual(result["statusCode"], 500)
        body = json.loads(result["body"])
        self.assertEqual(body["error"], "Failed to collect weather data")


class TestSecretsManager(unittest.TestCase):
    """Test Secrets Manager integration"""
    
    @patch('weather_collector_handler.secrets_client.get_secret_value')
    def test_get_api_keys_success(self, mock_get_secret):
        """Test successful API key retrieval"""
        mock_get_secret.return_value = {
            'SecretString': json.dumps({
                "openweathermap": "key1",
                "weatherapi": "key2"
            })
        }
        
        keys = weather_collector_handler.get_api_keys()
        
        self.assertEqual(keys["openweathermap"], "key1")
        self.assertEqual(keys["weatherapi"], "key2")
    
    @patch('weather_collector_handler.secrets_client.get_secret_value')
    def test_get_api_keys_failure(self, mock_get_secret):
        """Test API key retrieval failure"""
        from botocore.exceptions import ClientError
        mock_get_secret.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )
        
        keys = weather_collector_handler.get_api_keys()
        
        self.assertEqual(keys, {})


class TestDynamoDBStorage(unittest.TestCase):
    """Test DynamoDB storage operations"""
    
    @patch('weather_collector_handler.dynamodb.Table')
    def test_store_in_dynamodb_success(self, mock_table_class):
        """Test successful DynamoDB storage"""
        mock_table = Mock()
        mock_table_class.return_value = mock_table
        
        weather_data = {
            "temperature_avg": 25.0,
            "humidity_avg": 65,
            "sources": ["api1", "api2"]
        }
        quality_score = 0.85
        
        weather_collector_handler.store_in_dynamodb(weather_data, quality_score)
        
        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        
        # Check the item structure
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        
        self.assertEqual(item['location'], weather_collector_handler.LOCATION)
        self.assertIn('timestamp', item)
        self.assertIn('weather_data', item)
        self.assertEqual(item['data_quality_score'], Decimal('0.85'))
        self.assertIn('ttl', item)
    
    @patch('weather_collector_handler.dynamodb.Table')
    def test_store_in_dynamodb_failure(self, mock_table_class):
        """Test DynamoDB storage failure handling"""
        mock_table = Mock()
        mock_table.put_item.side_effect = Exception("DynamoDB Error")
        mock_table_class.return_value = mock_table
        
        with self.assertRaises(Exception):
            weather_collector_handler.store_in_dynamodb({}, 0.5)


if __name__ == '__main__':
    unittest.main()
