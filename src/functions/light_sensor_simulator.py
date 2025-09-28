import json
import boto3
import random
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
sqs = boto3.client('sqs')

# Environment variables
QUEUE_URL = os.environ['IOT_DATA_QUEUE_URL']
SENSOR_TYPE = os.environ.get('SENSOR_TYPE', 'light')
SENSOR_ID = os.environ.get('SENSOR_ID', 'light_sensor_001')
SENSOR_INTERVAL = int(os.environ.get('SENSOR_INTERVAL', '20'))

# Kyiv coordinates
KYIV_LAT = 50.4501
KYIV_LNG = 30.5234


class LightSensorSimulator:
    """Simulates light sensor readings"""

    def __init__(self):
        self.previous_light = 500.0  # Previous light reading in lux

    def generate_light_reading(self) -> float:
        """Generate realistic light reading in lux"""
        hour = datetime.now().hour
        minute = datetime.now().minute

        # Sunrise around 7 AM, sunset around 7 PM (simplified)
        if 6 <= hour <= 8:  # Dawn
            base_light = 100 + (hour - 6) * 200 + minute * 10
        elif 8 < hour < 18:  # Daylight
            # Peak at noon, with cloud variations
            noon_factor = 1 - abs(hour - 12) / 6  # Peak at noon
            cloud_factor = random.uniform(0.3, 1.0)  # Cloud coverage
            base_light = 1000 + noon_factor * 4000 * cloud_factor
        elif 18 <= hour <= 20:  # Dusk
            base_light = 1000 - (hour - 18) * 300 - minute * 10
        else:  # Night
            base_light = random.uniform(0.1, 10)  # Street lights, moon, etc.

        # Add weather variation
        weather_variation = random.uniform(0.7, 1.3)

        # Gradual change
        target_light = base_light * weather_variation
        self.previous_light += (target_light - self.previous_light) * 0.5

        return round(max(0.1, self.previous_light), 1)

    def create_sensor_message(self) -> Dict[str, Any]:
        """Create sensor data message"""
        # Add slight location variation
        lat_variation = random.uniform(-0.0005, 0.0005)
        lng_variation = random.uniform(-0.0005, 0.0005)

        return {
            "sensor_id": SENSOR_ID,
            "sensor_type": SENSOR_TYPE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "lat": round(KYIV_LAT + lat_variation, 6),
                "lng": round(KYIV_LNG + lng_variation, 6)
            },
            "value": self.generate_light_reading(),
            "unit": "lux",
            "metadata": {
                "interval_seconds": SENSOR_INTERVAL,
                "sensor_version": "1.0.0",
                "battery_level": random.uniform(75, 100),
                "calibration_date": "2024-01-15",
                "sensitivity": "high"
            }
        }


def handler(event, context):
    """Lambda handler for light sensor simulator"""
    try:
        simulator = LightSensorSimulator()
        sensor_data = simulator.create_sensor_message()

        # Send to SQS
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(sensor_data),
            MessageAttributes={
                'SensorType': {
                    'StringValue': SENSOR_TYPE,
                    'DataType': 'String'
                },
                'SensorId': {
                    'StringValue': SENSOR_ID,
                    'DataType': 'String'
                }
            }
        )

        logger.info(f"Light data sent to queue: {sensor_data['value']} lux")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Light data sent successfully',
                'sensor_data': sensor_data,
                'sqs_message_id': response['MessageId']
            })
        }

    except Exception as e:
        logger.error(f"Error in light sensor simulator: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }