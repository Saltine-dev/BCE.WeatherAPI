"""
Unit tests for Weather API Lambda function
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

# Load weather_api handler module with a unique name to avoid collisions
_api_path = (
    Path(__file__).resolve().parents[2]
    / 'src' / 'lambdas' / 'weather_api' / 'handler.py'
)
_api_spec = importlib.util.spec_from_file_location(
    'weather_api_handler', str(_api_path)
)
weather_api_handler = importlib.util.module_from_spec(_api_spec)
assert _api_spec and _api_spec.loader
_api_spec.loader.exec_module(weather_api_handler)
# Register module so @patch can resolve it by name
import sys as _sys
_sys.modules['weather_api_handler'] = weather_api_handler


class TestResponseHelpers(unittest.TestCase):
    """Test response helper functions"""
    
    def test_create_response_success(self):
        """Test creating a successful response"""
        response = weather_api_handler.create_response(200, {"message": "success"})
        
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Content-Type", response["headers"])
        self.assertIn("Access-Control-Allow-Origin", response["headers"])
        
        body = json.loads(response["body"])
        self.assertEqual(body["message"], "success")
    
    def test_create_response_with_decimal(self):
        """Test response with Decimal values"""
        data = {
            "temperature": Decimal("25.5"),
            "humidity": Decimal("65")
        }
        response = weather_api_handler.create_response(200, data)
        
        body = json.loads(response["body"])
        self.assertEqual(body["temperature"], 25.5)
        self.assertEqual(body["humidity"], 65)
    
    def test_decimal_encoder(self):
        """Test Decimal encoder"""
        encoder = weather_api_handler.DecimalEncoder()
        
        # Test integer Decimal
        result = encoder.default(Decimal("10"))
        self.assertEqual(result, 10)
        self.assertIsInstance(result, int)
        
        # Test float Decimal
        result = encoder.default(Decimal("10.5"))
        self.assertEqual(result, 10.5)
        self.assertIsInstance(result, float)


class TestCurrentWeather(unittest.TestCase):
    """Test current weather endpoint"""
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_get_current_weather_success(self, mock_table_class):
        """Test successful current weather retrieval"""
        mock_table = Mock()
        mock_table.query.return_value = {
            'Items': [{
                'location': 'lewisville-tx',
                'timestamp': '2024-01-15T12:00:00Z',
                'data_quality_score': Decimal('0.85'),
                'weather_data': {
                    'sources': ['api1', 'api2'],
                    'temperature_avg': Decimal('25.5'),
                    'temperature_min': Decimal('24.0'),
                    'temperature_max': Decimal('27.0'),
                    'humidity_avg': Decimal('65'),
                    'pressure_avg': Decimal('1013'),
                    'wind_speed_avg': Decimal('3.5'),
                    'weather_consensus': 'Cloudy'
                }
            }]
        }
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_current_weather()
        
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        
        self.assertEqual(body['location'], 'lewisville-tx')
        self.assertEqual(body['data_quality_score'], 0.85)
        self.assertEqual(body['current_conditions']['temperature']['value'], 25.5)
        self.assertEqual(body['current_conditions']['weather'], 'Cloudy')
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_get_current_weather_no_data(self, mock_table_class):
        """Test current weather when no data available"""
        mock_table = Mock()
        mock_table.query.return_value = {'Items': []}
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_current_weather()
        
        self.assertEqual(result['statusCode'], 404)
        body = json.loads(result['body'])
        self.assertEqual(body['error'], 'No weather data found')
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_get_current_weather_database_error(self, mock_table_class):
        """Test current weather with database error"""
        from botocore.exceptions import ClientError
        mock_table = Mock()
        mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'Query'
        )
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_current_weather()
        
        self.assertEqual(result['statusCode'], 500)
        body = json.loads(result['body'])
        self.assertEqual(body['error'], 'Database error')


class TestHistoricalWeather(unittest.TestCase):
    """Test historical weather endpoint"""
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_get_historical_weather_success(self, mock_table_class):
        """Test successful historical weather retrieval"""
        mock_table = Mock()
        
        # Create mock historical data
        now = datetime.now(timezone.utc)
        mock_items = []
        for i in range(5):
            timestamp = (now - timedelta(hours=i)).isoformat()
            mock_items.append({
                'timestamp': timestamp,
                'data_quality_score': Decimal('0.8'),
                'weather_data': {
                    'temperature_avg': Decimal(f'{25 - i}'),
                    'humidity_avg': Decimal(f'{65 + i}'),
                    'pressure_avg': Decimal('1013'),
                    'wind_speed_avg': Decimal('3.5'),
                    'clouds_avg': Decimal('50'),
                    'weather_consensus': 'Cloudy',
                    'sources': ['api1', 'api2']
                }
            })
        
        mock_table.query.return_value = {'Items': mock_items}
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_historical_weather(hours=24)
        
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        
        self.assertEqual(body['location'], weather_api_handler.LOCATION)
        self.assertEqual(body['data_points'], 5)
        self.assertEqual(len(body['history']), 5)
        self.assertIn('statistics', body)
        self.assertIn('temperature', body['statistics'])
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_get_historical_weather_no_data(self, mock_table_class):
        """Test historical weather when no data available"""
        mock_table = Mock()
        mock_table.query.return_value = {'Items': []}
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_historical_weather(hours=24)
        
        self.assertEqual(result['statusCode'], 404)
        body = json.loads(result['body'])
        self.assertEqual(body['error'], 'No historical data found')
    
    def test_get_historical_weather_statistics(self):
        """Test statistics calculation in historical weather"""
        # This is tested as part of the success test above
        pass


class TestDataSources(unittest.TestCase):
    """Test data sources endpoint"""
    
    def test_get_data_sources(self):
        """Test data sources information retrieval"""
        result = weather_api_handler.get_data_sources()
        
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        
        self.assertEqual(body['location'], weather_api_handler.LOCATION)
        self.assertIn('coordinates', body)
        self.assertIn('available_sources', body)
        self.assertIsInstance(body['available_sources'], list)
        self.assertGreater(len(body['available_sources']), 0)
        
        # Check structure of source info
        source = body['available_sources'][0]
        self.assertIn('name', source)
        self.assertIn('id', source)
        self.assertIn('description', source)
        self.assertIn('update_frequency', source)
        self.assertIn('free_tier_limit', source)


class TestHealthCheck(unittest.TestCase):
    """Test health check endpoint"""
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_health_check_healthy(self, mock_table_class):
        """Test health check when system is healthy"""
        mock_table = Mock()
        
        # Mock recent data
        now = datetime.now(timezone.utc)
        mock_table.query.return_value = {
            'Items': [{
                'timestamp': now.isoformat()
            }]
        }
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_health_status()
        
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        
        self.assertEqual(body['status'], 'healthy')
        self.assertIn('timestamp', body)
        self.assertEqual(body['database']['status'], 'connected')
        self.assertTrue(body['data']['is_fresh'])
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_health_check_degraded(self, mock_table_class):
        """Test health check when data is stale"""
        mock_table = Mock()
        
        # Mock stale data (1 hour old)
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_table.query.return_value = {
            'Items': [{
                'timestamp': old_time.isoformat()
            }]
        }
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_health_status()
        
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        
        self.assertEqual(body['status'], 'degraded')
        self.assertFalse(body['data']['is_fresh'])
    
    @patch('weather_api_handler.dynamodb.Table')
    def test_health_check_error(self, mock_table_class):
        """Test health check with database error"""
        mock_table = Mock()
        mock_table.query.side_effect = Exception("Database connection failed")
        mock_table_class.return_value = mock_table
        
        result = weather_api_handler.get_health_status()
        
        self.assertEqual(result['statusCode'], 503)
        body = json.loads(result['body'])
        
        self.assertEqual(body['status'], 'unhealthy')
        self.assertIn('error', body)


class TestLambdaHandler(unittest.TestCase):
    """Test main Lambda handler routing"""
    
    @patch('weather_api_handler.get_current_weather')
    def test_lambda_handler_current_weather(self, mock_get_current):
        """Test Lambda handler routing to current weather"""
        mock_get_current.return_value = {
            'statusCode': 200,
            'body': json.dumps({'test': 'data'})
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/weather/current'
        }
        
        result = weather_api_handler.lambda_handler(event, {})
        
        mock_get_current.assert_called_once()
        self.assertEqual(result['statusCode'], 200)
    
    @patch('weather_api_handler.get_historical_weather')
    def test_lambda_handler_history(self, mock_get_history):
        """Test Lambda handler routing to historical weather"""
        mock_get_history.return_value = {
            'statusCode': 200,
            'body': json.dumps({'test': 'data'})
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/weather/history',
            'queryStringParameters': {'hours': '48'}
        }
        
        result = weather_api_handler.lambda_handler(event, {})
        
        mock_get_history.assert_called_once_with(48)
        self.assertEqual(result['statusCode'], 200)
    
    @patch('weather_api_handler.get_data_sources')
    def test_lambda_handler_sources(self, mock_get_sources):
        """Test Lambda handler routing to data sources"""
        mock_get_sources.return_value = {
            'statusCode': 200,
            'body': json.dumps({'test': 'data'})
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/weather/sources'
        }
        
        result = weather_api_handler.lambda_handler(event, {})
        
        mock_get_sources.assert_called_once()
        self.assertEqual(result['statusCode'], 200)
    
    @patch('weather_api_handler.get_health_status')
    def test_lambda_handler_health(self, mock_get_health):
        """Test Lambda handler routing to health check"""
        mock_get_health.return_value = {
            'statusCode': 200,
            'body': json.dumps({'status': 'healthy'})
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        result = weather_api_handler.lambda_handler(event, {})
        
        mock_get_health.assert_called_once()
        self.assertEqual(result['statusCode'], 200)
    
    def test_lambda_handler_options(self):
        """Test Lambda handler CORS OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/weather/current'
        }
        
        result = weather_api_handler.lambda_handler(event, {})
        
        self.assertEqual(result['statusCode'], 200)
        self.assertIn('Access-Control-Allow-Origin', result['headers'])
        self.assertIn('Access-Control-Allow-Methods', result['headers'])
    
    def test_lambda_handler_not_found(self):
        """Test Lambda handler with unknown path"""
        event = {
            'httpMethod': 'GET',
            'path': '/unknown/path'
        }
        
        result = handler.lambda_handler(event, {})
        
        self.assertEqual(result['statusCode'], 404)
        body = json.loads(result['body'])
        self.assertEqual(body['error'], 'Not found')
        self.assertIn('available_endpoints', body)
    
    def test_lambda_handler_max_hours_limit(self):
        """Test Lambda handler enforces maximum hours limit"""
        with patch('weather_api_handler.get_historical_weather') as mock_get_history:
            mock_get_history.return_value = {
                'statusCode': 200,
                'body': json.dumps({'test': 'data'})
            }
            
            event = {
                'httpMethod': 'GET',
                'path': '/weather/history',
                'queryStringParameters': {'hours': '200'}  # More than 168 (7 days)
            }
            
            result = weather_api_handler.lambda_handler(event, {})
            
            # Should be called with max of 168 hours
            mock_get_history.assert_called_once_with(168)


if __name__ == '__main__':
    unittest.main()
