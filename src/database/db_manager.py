import json
import boto3
import pymysql
import os
import logging
from typing import Dict, Optional


logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client('secretsmanager')


DB_SECRET_ARN = os.environ['DB_SECRET_ARN']


class DatabaseManager:
    """Manages MySQL database connections and operations"""

    def __init__(self):
        self.connection = None
        self.db_config = None

    def get_database_credentials(self) -> Dict[str, str]:
        """Retrieve database credentials from AWS Secrets Manager"""
        if self.db_config:
            return self.db_config

        try:
            response = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
            secret = json.loads(response['SecretString'])

            self.db_config = {
                'host': secret['DB_HOST'],
                'user': secret['DB_USER'],
                'password': secret['DB_PASSWORD'],
                'database': secret['DB_NAME'],
                'port': int(secret.get('DB_PORT', 3306)),
                'charset': 'utf8mb4',
                'autocommit': True,
                'connect_timeout': 30,
                'read_timeout': 30,
                'write_timeout': 30
            }
            return self.db_config

        except Exception as e:
            logger.error(f"Failed to retrieve database credentials: {e}")
            raise

    def get_connection(self):
        """Get database connection with retry logic"""
        if self.connection and self.connection.open:
            try:
                self.connection.ping(reconnect=True)
                return self.connection
            except:
                self.connection = None

        try:
            config = self.get_database_credentials()
            self.connection = pymysql.connect(**config)
            logger.info("Database connection established successfully")
            return self.connection

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def execute_query(self, query: str, params: Optional[tuple] = None, fetch_results: bool = False):
        """Execute database query with error handling"""
        try:
            conn = self.get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, params)

                if fetch_results:
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return cursor.rowcount

        except Exception as e:
            logger.error(f"Database query execution failed: {e}")
            raise

    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
