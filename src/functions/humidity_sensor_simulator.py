import json
import boto3
import random
import os
import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
sqs = boto3.client('sqs')

# Environment variables
QUEUE_URL = os.environ['IOT_DATA_QUEUE_URL']
SENSOR_TYPE = os.environ.get('SENSOR_TYPE', 'humidity')
SENSOR_ID = os.environ.get('SENSOR_ID', 'humidity_sensor_001')
SENSOR_INTERVAL = int(os.environ.get('SENSOR_INTERVAL', '15'))

# Kyiv coordinates
KYIV_LAT = 50.4501
KYIV_LNG = 30.5234


class HumiditySensorSimulator:
    """Simulates humidity sensor readings"""

    def __init__(self):
        self.previous_humidity = 55.0  # Base humidity percentage

    def generate_humidity_reading(self) -> float:
        """Generate realistic humidity reading"""
        # Simulate daily humidity variation (higher at night/morning)
        hour = datetime.now().hour
        daily_variation = 10 * math.cos((hour - 6) * math.pi / 12)  # Lower during day

        # Seasonal variation (higher in summer)
        month = datetime.now().month
        seasonal_variation = 15 if 6 <= month <= 8 else 0  # Higher in summer

        # Weather simulation (random weather events)
        weather_factor = random.choice([0, 0, 0, 15, 25])  # Occasional rain/fog

        # Base humidity with variations
        base_humidity = 50 + daily_variation + seasonal_variation
        random_change = random.uniform(-3, 3)

        # Gradual change to avoid sudden jumps
        target_humidity = base_humidity + weather_factor + random_change
        self.previous_humidity += (target_humidity - self.previous_humidity) * 0.4

        # Keep within realistic bounds
        return round(max(20, min(95, self.previous_humidity)), 1)

    def create_sensor_message(self) -> Dict[str, Any]:
        """Create sensor data message"""
        # Add slight location variation
        lat_variation = random.uniform(-0.0008, 0.0008)
        lng_variation = random.uniform(-0.0008, 0.0008)

        return {
            "sensor_id": SENSOR_ID,
            "sensor_type": SENSOR_TYPE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "lat": round(KYIV_LAT + lat_variation, 6),
                "lng": round(KYIV_LNG + lng_variation, 6)
            },
            "value": self.generate_humidity_reading(),
            "unit": "%",
            "metadata": {
                "interval_seconds": SENSOR_INTERVAL,
                "sensor_version": "1.0.0",
                "battery_level": random.uniform(80, 100),
                "signal_strength": random.uniform(-70, -40)
            }
        }


def handler(event, context):
    """Lambda handler for humidity sensor simulator"""
    try:
        simulator = HumiditySensorSimulator()
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

        logger.info(f"Humidity data sent to queue: {sensor_data['value']}%")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Humidity data sent successfully',
                'sensor_data': sensor_data,
                'sqs_message_id': response['MessageId']
            })
        }

    except Exception as e:
        logger.error(f"Error in humidity sensor simulator: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }