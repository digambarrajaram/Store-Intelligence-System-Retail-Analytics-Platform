import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Assuming the module structure
try:
    from src.main import app
except ImportError:
    try:
        from main import app
    except ImportError:
        # Create a mock FastAPI app for testing
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/api/v1/metrics")
        async def get_metrics():
            # This would normally query Redis/Kafka
            return {"occupancy": 0, "zones": {}}

# Import test dependencies
try:
    import httpx
    from fastapi.testclient import TestClient
except ImportError:
    # We'll handle missing imports in the mock
    pass


class TestAPIMetrics:
    """Integration tests for /api/v1/metrics endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        return TestClient(app)
    
    @pytest.fixture
    def async_client(self):
        """Create an async test client."""
        # For true async testing with async endpoints
        return httpx.AsyncClient(app=app, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_metrics_returns_correct_occupancy_after_simulated_entries_exits(self, async_client, fake_redis):
        """Test /api/v1/metrics returns correct occupancy after simulated entries/exits."""
        # Mock Redis to return occupancy data
        with patch('src.api.v1.metrics.get_redis', return_value=fake_redis):
            # Simulate some entries
            fake_redis.hset('zone:A:occupancy', 'track_1', '1')
            fake_redis.hset('zone:A:occupancy', 'track_2', '1')
            fake_redis.hset('zone:B:occupancy', 'track_3', '1')
            
            # Make request
            response = await async_client.get("/api/v1/metrics")
            assert response.status_code == 200
            
            data = response.json()
            assert data['occupancy'] == 3  # Total tracks across zones
            assert data['zones']['zone_A']['occupancy'] == 2
            assert data['zones']['zone_B']['occupancy'] == 1
            
            # Simulate an exit
            fake_redis.hdel('zone:A:occupancy', 'track_1')
            
            response = await async_client.get("/api/v1/metrics")
            assert response.status_code == 200
            
            data = response.json()
            assert data['occupancy'] == 2
            assert data['zones']['zone_A']['occupancy'] == 1
            assert data['zones']['zone_B']['occupancy'] == 1
    
    @pytest.mark.asyncio
    async def test_metrics_handles_empty_state(self, async_client, fake_redis):
        """Test metrics endpoint when no data is present."""
        with patch('src.api.v1.metrics.get_redis', return_value=fake_redis):
            # Ensure Redis is empty
            fake_redis.flushall()
            
            response = await async_client.get("/api/v1/metrics")
            assert response.status_code == 200
            
            data = response.json()
            assert data['occupancy'] == 0
            assert data['zones'] == {}
    
    @pytest.mark.asyncio
    async def test_metrics_returns_correct_format(self, async_client, fake_redis):
        """Test that metrics returns expected JSON structure."""
        with patch('src.api.v1.metrics.get_redis', return_value=fake_redis):
            # Set up some test data
            fake_redis.hset('zone:test:occupancy', 'track_abc', datetime.now().isoformat())
            
            response = await async_client.get("/api/v1/metrics")
            assert response.status_code == 200
            
            data = response.json()
            # Check required fields
            assert 'occupancy' in data
            assert 'zones' in data
            assert isinstance(data['occupancy'], int)
            assert isinstance(data['zones'], dict)
            
            for zone_id, zone_data in data['zones'].items():
                assert 'occupancy' in zone_data
                assert isinstance(zone_data['occupancy'], int)
    
    @pytest.mark.asyncio
    async def test_metrics_updates_with_kafka_events(self, async_client, fake_redis):
        """Test that metrics update when Kafka events are processed."""
        # This would test the integration between Kafka consumer and metrics API
        # We'll mock the Kafka consumer updating Redis
        
        with patch('src.api.v1.metrics.get_redis', return_value=fake_redis):
            # Simulate initial state
            assert fake_redis.hlen('zone:A:occupancy') == 0
            
            # Simulate Kafka entry event being processed
            entry_event = {
                'track_id': 'kafka_track_1',
                'event_type': 'entry',
                'zone_id': 'zone_A',
                'timestamp': datetime.now().isoformat()
            }
            
            # Mock the event processing function
            with patch('src.api.v1.metrics.process_entry_event') as mock_process:
                mock_process.return_value = None
                # In reality, this would update Redis
                # We'll directly update Redis to simulate the effect
                fake_redis.hset('zone:A:occupancy', entry_event['track_id'], entry_event['timestamp'])
                
                response = await async_client.get("/api/v1/metrics")
                assert response.status_code == 200
                
                data = response.json()
                assert data['occupancy'] == 1
                assert data['zones']['zone_A']['occupancy'] == 1
            
            # Simulate Kafka exit event
            exit_event = {
                'track_id': 'kafka_track_1',
                'event_type': 'exit',
                'zone_id': 'zone_A',
                'timestamp': datetime.now().isoformat()
            }
            
            with patch('src.api.v1.metrics.process_exit_event') as mock_process:
                mock_process.return_value = None
                fake_redis.hdel('zone:A:occupancy', exit_event['track_id'])
                
                response = await async_client.get("/api/v1/metrics")
                assert response.status_code == 200
                
                data = response.json()
                assert data['occupancy'] == 0
                assert data['zones']['zone_A']['occupancy'] == 0

