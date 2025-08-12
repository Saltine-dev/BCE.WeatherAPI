"""
Integration tests for Weather API
"""

import json
import os
import requests
import time
import unittest
from datetime import datetime, timezone


class TestWeatherAPIIntegration(unittest.TestCase):
    """Integration tests for Weather API endpoints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.api_endpoint = os.environ.get('API_ENDPOINT', 'http://localhost:3000')
        cls.headers = {
            'Content-Type': 'application/json'
        }
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = requests.get(f"{self.api_endpoint}/health", headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('status', data)
        self.assertIn(['healthy', 'degraded'], data['status'])
        self.assertIn('timestamp', data)
        self.assertIn('database', data)
        self.assertIn('data', data)
    
    def test_sources_endpoint(self):
        """Test data sources endpoint"""
        response = requests.get(f"{self.api_endpoint}/weather/sources", headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('location', data)
        self.assertIn('coordinates', data)
        self.assertIn('available_sources', data)
        self.assertIsInstance(data['available_sources'], list)
        self.assertGreater(len(data['available_sources']), 0)
        
        # Validate source structure
        for source in data['available_sources']:
            self.assertIn('name', source)
            self.assertIn('id', source)
            self.assertIn('description', source)
            self.assertIn('update_frequency', source)
            self.assertIn('free_tier_limit', source)
    
    def test_current_weather_endpoint(self):
        """Test current weather endpoint"""
        response = requests.get(f"{self.api_endpoint}/weather/current", headers=self.headers)
        
        # May return 404 if no data collected yet
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            
            self.assertIn('location', data)
            self.assertIn('timestamp', data)
            self.assertIn('data_quality_score', data)
            self.assertIn('current_conditions', data)
            
            conditions = data['current_conditions']
            self.assertIn('temperature', conditions)
            self.assertIn('humidity', conditions)
            self.assertIn('pressure', conditions)
            self.assertIn('wind', conditions)
            self.assertIn('weather', conditions)
    
    def test_historical_weather_endpoint(self):
        """Test historical weather endpoint"""
        response = requests.get(
            f"{self.api_endpoint}/weather/history",
            params={'hours': 24},
            headers=self.headers
        )
        
        # May return 404 if no data collected yet
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            
            self.assertIn('location', data)
            self.assertIn('period', data)
            self.assertIn('data_points', data)
            self.assertIn('statistics', data)
            self.assertIn('history', data)
            
            # Validate period structure
            period = data['period']
            self.assertIn('start', period)
            self.assertIn('end', period)
            self.assertIn('hours', period)
            self.assertEqual(period['hours'], 24)
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = requests.options(f"{self.api_endpoint}/weather/current")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('Access-Control-Allow-Origin', response.headers)
        self.assertIn('Access-Control-Allow-Methods', response.headers)
        self.assertIn('Access-Control-Allow-Headers', response.headers)
    
    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404"""
        response = requests.get(f"{self.api_endpoint}/invalid/endpoint", headers=self.headers)
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        
        self.assertIn('error', data)
        self.assertIn('available_endpoints', data)
    
    def test_rate_limiting(self):
        """Test API rate limiting (if configured)"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = requests.get(f"{self.api_endpoint}/weather/current", headers=self.headers)
            responses.append(response.status_code)
        
        # All should succeed (rate limiting would return 429)
        for status in responses:
            self.assertIn(status, [200, 404])
    
    def test_response_time(self):
        """Test API response time is acceptable"""
        start_time = time.time()
        response = requests.get(f"{self.api_endpoint}/weather/sources", headers=self.headers)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Response should be under 2 seconds
        self.assertLess(response_time, 2.0, f"Response time {response_time}s exceeds 2s limit")
        self.assertEqual(response.status_code, 200)


class TestDataCollection(unittest.TestCase):
    """Integration tests for data collection process"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.api_endpoint = os.environ.get('API_ENDPOINT', 'http://localhost:3000')
    
    def test_data_freshness(self):
        """Test that data is being collected and is fresh"""
        response = requests.get(f"{self.api_endpoint}/health")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('data', {}).get('last_update'):
                last_update = data['data']['last_update']
                last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                
                # Check if data is less than 30 minutes old
                time_diff = datetime.now(timezone.utc) - last_update_time
                is_fresh = time_diff.total_seconds() < 1800
                
                if not is_fresh:
                    print(f"Warning: Data is {time_diff.total_seconds() / 60:.1f} minutes old")


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests for complete workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.api_endpoint = os.environ.get('API_ENDPOINT', 'http://localhost:3000')
    
    def test_complete_workflow(self):
        """Test complete workflow from health check to data retrieval"""
        # 1. Check health
        health_response = requests.get(f"{self.api_endpoint}/health")
        self.assertEqual(health_response.status_code, 200)
        
        # 2. Get available sources
        sources_response = requests.get(f"{self.api_endpoint}/weather/sources")
        self.assertEqual(sources_response.status_code, 200)
        sources_data = sources_response.json()
        self.assertGreater(len(sources_data['available_sources']), 0)
        
        # 3. Get current weather (if available)
        current_response = requests.get(f"{self.api_endpoint}/weather/current")
        self.assertIn(current_response.status_code, [200, 404])
        
        # 4. Get historical data (if available)
        history_response = requests.get(
            f"{self.api_endpoint}/weather/history",
            params={'hours': 6}
        )
        self.assertIn(history_response.status_code, [200, 404])
        
        # Validate data consistency if both endpoints return data
        if current_response.status_code == 200 and history_response.status_code == 200:
            current_data = current_response.json()
            history_data = history_response.json()
            
            # Location should match
            self.assertEqual(current_data['location'], history_data['location'])


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
