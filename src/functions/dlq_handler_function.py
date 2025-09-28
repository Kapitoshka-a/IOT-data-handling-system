import json
import boto3
import logging
from datetime import datetime


logger = logging.getLogger()
logger.setLevel(logging.INFO)

cloudwatch = boto3.client('cloudwatch')


def handler(event, context):
    """
    Handler for processing messages from Dead Letter Queue
    """
    logger.info(f"Processing {len(event.get('Records', []))} DLQ messages")

    for record in event.get('Records', []):
        try:
            message_body = record['body']
            message_attributes = record.get('messageAttributes', {})

            if isinstance(message_body, str):
                dlq_data = json.loads(message_body)
            else:
                dlq_data = message_body

            # Log the failure
            error_reason = dlq_data.get('error_reason', 'Unknown error')
            failed_at = dlq_data.get('failed_at', datetime.utcnow().isoformat())
            original_message = dlq_data.get('original_message', '')

            logger.warning(f"DLQ Message processed - Error: {error_reason}, Failed at: {failed_at}")

            # Send CloudWatch metric
            cloudwatch.put_metric_data(
                Namespace='IoT/DataProcessing',
                MetricData=[
                    {
                        'MetricName': 'FailedMessages',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'ErrorType',
                                'Value': error_reason[:50]
                            }
                        ]
                    }
                ]
            )

        except Exception as e:
            logger.error(f"Error processing DLQ message: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_dlq_messages': len(event.get('Records', [])),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    }