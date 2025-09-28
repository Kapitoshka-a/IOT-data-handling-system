import json
import boto3
import os
import logging
from datetime import datetime
from typing import Dict, Any

from database.db_manager import DatabaseManager

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
secrets_client = boto3.client('secretsmanager')
sqs = boto3.client('sqs')

# Environment variables
DB_SECRET_ARN = os.environ['DB_SECRET_ARN']
DLQ_URL = os.environ['IOT_DLQ_URL']
TEMPERATURE_TABLE = os.environ['TEMPERATURE_TABLE']
HUMIDITY_TABLE = os.environ['HUMIDITY_TABLE']
LIGHT_TABLE = os.environ['LIGHT_TABLE']
ALL_SENSORS_TABLE = os.environ['ALL_SENSORS_TABLE']


db_manager = DatabaseManager()


def create_database_tables():
    """Create all required tables if they don't exist"""
    try:
        # Temperature sensor table
        temperature_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TEMPERATURE_TABLE} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            sensor_id VARCHAR(100) NOT NULL,
            timestamp DATETIME NOT NULL,
            location_lat DECIMAL(10, 8) NOT NULL,
            location_lng DECIMAL(11, 8) NOT NULL,
            temperature_celsius DECIMAL(5, 2) NOT NULL,
            metadata JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sensor_timestamp (sensor_id, timestamp),
            INDEX idx_timestamp (timestamp),
            INDEX idx_location (location_lat, location_lng)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        # Humidity sensor table
        humidity_table_query = f"""
        CREATE TABLE IF NOT EXISTS {HUMIDITY_TABLE} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            sensor_id VARCHAR(100) NOT NULL,
            timestamp DATETIME NOT NULL,
            location_lat DECIMAL(10, 8) NOT NULL,
            location_lng DECIMAL(11, 8) NOT NULL,
            humidity_percentage DECIMAL(5, 2) NOT NULL,
            metadata JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sensor_timestamp (sensor_id, timestamp),
            INDEX idx_timestamp (timestamp),
            INDEX idx_location (location_lat, location_lng)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        # Light sensor table
        light_table_query = f"""
        CREATE TABLE IF NOT EXISTS {LIGHT_TABLE} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            sensor_id VARCHAR(100) NOT NULL,
            timestamp DATETIME NOT NULL,
            location_lat DECIMAL(10, 8) NOT NULL,
            location_lng DECIMAL(11, 8) NOT NULL,
            light_lux DECIMAL(8, 2) NOT NULL,
            metadata JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sensor_timestamp (sensor_id, timestamp),
            INDEX idx_timestamp (timestamp),
            INDEX idx_location (location_lat, location_lng)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        # All sensors combined table
        all_sensors_table_query = f"""
        CREATE TABLE IF NOT EXISTS {ALL_SENSORS_TABLE} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            sensor_id VARCHAR(100) NOT NULL,
            sensor_type VARCHAR(50) NOT NULL,
            timestamp DATETIME NOT NULL,
            location_lat DECIMAL(10, 8) NOT NULL,
            location_lng DECIMAL(11, 8) NOT NULL,
            sensor_value DECIMAL(10, 3) NOT NULL,
            unit VARCHAR(20) NOT NULL,
            metadata JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_sensor_type_timestamp (sensor_type, timestamp),
            INDEX idx_sensor_timestamp (sensor_id, timestamp),
            INDEX idx_timestamp (timestamp),
            INDEX idx_location (location_lat, location_lng)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        # Execute table creation queries
        db_manager.execute_query(temperature_table_query)
        db_manager.execute_query(humidity_table_query)
        db_manager.execute_query(light_table_query)
        db_manager.execute_query(all_sensors_table_query)

        logger.info("All database tables created/verified successfully")

    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


class SensorDataProcessor:
    """Processes and saves sensor data to appropriate tables"""

    def __init__(self):
        create_database_tables()

    def validate_sensor_data(self, data: Dict[str, Any]) -> bool:
        """Validate incoming sensor data"""
        required_fields = ['sensor_id', 'sensor_type', 'timestamp', 'location', 'value', 'unit']

        # Check required fields
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate data types and values
        try:
            # Validate numeric value
            float(data['value'])

            # Validate timestamp
            datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))

            # Validate location
            location = data['location']
            if not isinstance(location, dict) or 'lat' not in location or 'lng' not in location:
                logger.error("Invalid location format")
                return False

            float(location['lat'])
            float(location['lng'])

            # Validate sensor type
            if data['sensor_type'] not in ['temperature', 'humidity', 'light']:
                logger.error(f"Unknown sensor type: {data['sensor_type']}")
                return False

        except (ValueError, TypeError) as e:
            logger.error(f"Data validation error: {e}")
            return False

        return True

    def process_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Process and save sensor data to appropriate tables"""
        try:
            if not self.validate_sensor_data(sensor_data):
                return False

            # Convert timestamp to MySQL format
            dt = datetime.fromisoformat(sensor_data['timestamp'].replace('Z', '+00:00'))
            mysql_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')

            # Extract common fields
            common_data = {
                'sensor_id': sensor_data['sensor_id'],
                'timestamp': mysql_timestamp,
                'location_lat': float(sensor_data['location']['lat']),
                'location_lng': float(sensor_data['location']['lng']),
                'metadata': json.dumps(sensor_data.get('metadata', {}))
            }

            # Save to specific sensor table
            self.save_to_specific_table(sensor_data, common_data)

            # Save to general all sensors table
            self.save_to_all_sensors_table(sensor_data, common_data)

            logger.info(f"Successfully processed {sensor_data['sensor_type']} data from {sensor_data['sensor_id']}")
            return True

        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
            return False

    def save_to_specific_table(self, sensor_data: Dict[str, Any], common_data: Dict[str, Any]):
        """Save data to sensor-specific table"""
        sensor_type = sensor_data['sensor_type']
        value = float(sensor_data['value'])

        if sensor_type == 'temperature':
            query = f"""
            INSERT INTO {TEMPERATURE_TABLE} 
            (sensor_id, timestamp, location_lat, location_lng, temperature_celsius, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                common_data['sensor_id'],
                common_data['timestamp'],
                common_data['location_lat'],
                common_data['location_lng'],
                value,
                common_data['metadata']
            )

        elif sensor_type == 'humidity':
            query = f"""
            INSERT INTO {HUMIDITY_TABLE}
            (sensor_id, timestamp, location_lat, location_lng, humidity_percentage, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                common_data['sensor_id'],
                common_data['timestamp'],
                common_data['location_lat'],
                common_data['location_lng'],
                value,
                common_data['metadata']
            )

        elif sensor_type == 'light':
            query = f"""
            INSERT INTO {LIGHT_TABLE}
            (sensor_id, timestamp, location_lat, location_lng, light_lux, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                common_data['sensor_id'],
                common_data['timestamp'],
                common_data['location_lat'],
                common_data['location_lng'],
                value,
                common_data['metadata']
            )

        db_manager.execute_query(query, params)

    def save_to_all_sensors_table(self, sensor_data: Dict[str, Any], common_data: Dict[str, Any]):
        """Save data to general all sensors table"""
        query = f"""
        INSERT INTO {ALL_SENSORS_TABLE}
        (sensor_id, sensor_type, timestamp, location_lat, location_lng, sensor_value, unit, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        params = (
            common_data['sensor_id'],
            sensor_data['sensor_type'],
            common_data['timestamp'],
            common_data['location_lat'],
            common_data['location_lng'],
            float(sensor_data['value']),
            sensor_data['unit'],
            common_data['metadata']
        )

        db_manager.execute_query(query, params)


def send_to_dlq(message_body: str, error_reason: str, original_message_attributes: Dict = None):
    """Send failed message to Dead Letter Queue"""
    try:
        dlq_message = {
            'original_message': message_body,
            'error_reason': error_reason,
            'failed_at': datetime.utcnow().isoformat() + 'Z',
            'processing_attempt': 'save_calculated_data_function'
        }

        message_attributes = {
            'ErrorReason': {
                'StringValue': error_reason,
                'DataType': 'String'
            },
            'FailedFunction': {
                'StringValue': 'save_calculated_data_function',
                'DataType': 'String'
            }
        }

        if original_message_attributes:
            message_attributes.update(original_message_attributes)

        sqs.send_message(
            QueueUrl=DLQ_URL,
            MessageBody=json.dumps(dlq_message),
            MessageAttributes=message_attributes
        )

        logger.info(f"Message sent to DLQ: {error_reason}")

    except Exception as e:
        logger.error(f"Failed to send message to DLQ: {e}")


def handler(event, context):
    """
    Main Lambda handler for processing SQS messages
    """
    logger.info(f"Processing batch of {len(event.get('Records', []))} SQS records")

    processor = SensorDataProcessor()
    batch_item_failures = []
    successful_records = 0
    failed_records = 0

    for record in event.get('Records', []):
        message_id = record.get('messageId')
        receipt_handle = record.get('receiptHandle')

        try:
            # Parse message body
            message_body = record['body']

            if isinstance(message_body, str):
                sensor_data = json.loads(message_body)
            else:
                sensor_data = message_body

            # Process the sensor data
            if processor.process_sensor_data(sensor_data):
                successful_records += 1
                logger.info(f"Successfully processed message {message_id}")
            else:
                failed_records += 1
                batch_item_failures.append({"itemIdentifier": message_id})
                send_to_dlq(
                    message_body,
                    "Sensor data validation or processing failed",
                    record.get('messageAttributes', {})
                )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for message {message_id}: {e}")
            failed_records += 1
            batch_item_failures.append({"itemIdentifier": message_id})
            send_to_dlq(
                record.get('body', ''),
                f"JSON decode error: {str(e)}",
                record.get('messageAttributes', {})
            )

        except Exception as e:
            logger.error(f"Unexpected error processing message {message_id}: {e}")
            failed_records += 1
            batch_item_failures.append({"itemIdentifier": message_id})
            send_to_dlq(
                record.get('body', ''),
                f"Processing error: {str(e)}",
                record.get('messageAttributes', {})
            )

    # Close database connection
    db_manager.close_connection()

    logger.info(f"Batch processing complete. Success: {successful_records}, Failed: {failed_records}")

    # Return batch item failures for SQS to retry
    return {
        "batchItemFailures": batch_item_failures
    }
