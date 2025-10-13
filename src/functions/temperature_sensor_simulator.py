import json
import math

import boto3
import random
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any


logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
sqs = boto3.client('sqs')

# Environment variables
QUEUE_URL = os.environ['IOT_DATA_QUEUE_URL']
SENSOR_TYPE = os.environ.get('SENSOR_TYPE', 'temperature')
SENSOR_ID = os.environ.get('SENSOR_ID', 'temp_sensor_001')
SENSOR_INTERVAL = int(os.environ.get('SENSOR_INTERVAL', '10'))


KYIV_LAT = 50.4501
KYIV_LNG = 30.5234


class TemperatureSensorSimulator:
    """Simulates temperature sensor readings"""

    def __init__(self):
        self.base_temperature = 22.0  # Base temperature in Celsius
        self.previous_temp = self.base_temperature

    def generate_temperature_reading(self) -> float:
        """Generate realistic temperature reading with gradual changes"""
        # Simulate daily temperature variation
        hour = datetime.now().hour
        daily_variation = 5 * math.sin((hour - 6) * math.pi / 12)  # Peak at 2 PM

        # Add some randomness but keep it realistic
        random_change = random.uniform(-1.5, 1.5)
        seasonal_base = 15.0 if 11 <= datetime.now().month <= 3 else 25.0  # Winter/Summer

        # Calculate new temperature with gradual change
        target_temp = seasonal_base + daily_variation + random_change
        self.previous_temp += (target_temp - self.previous_temp) * 0.3  # Gradual change

        return round(self.previous_temp, 2)

    def create_sensor_message(self) -> Dict[str, Any]:
        """Create sensor data message"""
        # Add slight location variation to simulate sensor movement
        lat_variation = random.uniform(-0.001, 0.001)
        lng_variation = random.uniform(-0.001, 0.001)

        return {
            "sensor_id": SENSOR_ID,
            "sensor_type": SENSOR_TYPE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "lat": round(KYIV_LAT + lat_variation, 6),
                "lng": round(KYIV_LNG + lng_variation, 6)
            },
            "value": self.generate_temperature_reading(),
            "unit": "°C",
            "metadata": {
                "interval_seconds": SENSOR_INTERVAL,
                "sensor_version": "1.0.0",
                "battery_level": random.uniform(85, 100)
            }
        }


def handler(event, context):
    """Lambda handler for temperature sensor simulator"""
    try:
        simulator = TemperatureSensorSimulator()
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

        logger.info(f"Temperature data sent to queue: {sensor_data['value']}°C")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Temperature data sent successfully',
                'sensor_data': sensor_data,
                'sqs_message_id': response['MessageId']
            })
        }

    except Exception as e:
        logger.error(f"Error in temperature sensor simulator: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
