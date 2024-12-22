import boto3
import json
import asyncio
import aiohttp
import logging
from models import EventStatus
from push_notif_service import send_push_notification
# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=localstack_endpoint)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=localstack_endpoint)
dynamodb_table = dynamodb_client.Table('event')

# SQS queue URLs
CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_critical"
NON_CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_non_critical"
DLQ_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/dlq"

# Configure logging
logging.basicConfig(level=logging.INFO)

def apply_business_logic(event_payload):
    """
    Applies business logic to determine which clients should receive the notification.
    """
    # Example business logic: Send to clients with a specific attribute
    target_clients = []
    if event_payload.get('event_type') == 'important_update':
        target_clients = event_payload.get('target_clients', [])
    return target_clients

async def process_message(message):
    """
    Processes a single SQS message and sends push notifications based on business logic.
    """
    body = json.loads(message['Body'])
    event_payload = json.loads(body['Message'])

    event_id = event_payload.get('event_id')
    target_clients = apply_business_logic(event_payload)
    notification_message = f"Event {event_payload.get('event_name', 'unknown')} occurred."

    # Update DynamoDB to IN_PROGRESS status
    dynamodb_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': EventStatus.IN_PROGRESS}
    )

    success = True
    for client_id in target_clients:
        try:
            status = await send_push_notification(client_id, notification_message)
            logging.info(f"Push notification sent to client {client_id}")
        except Exception as e:
            logging.error(f"Error sending push notification to client {client_id}: {e}")
            success = False

    # Update final status in DynamoDB
    final_status = EventStatus.SUCCESS if success else EventStatus.FAILED
    dynamodb_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': final_status}
    )

    # If failed, send to DLQ
    if not success:
        sqs_client.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(event_payload))

async def listen_to_sqs_priority():
    """
    Continuously listens to the SQS queue and processes messages.
    """
    while True:
        logging.info("Listening to SQS queue...")
        critical_response = sqs_client.receive_message(
            QueueUrl=CRITICAL_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10
        )
        if critical_response.get('Messages', []):
            logging.info(f"Processing {len(critical_response.get('Messages', []))} critical messages in parallel")
            # Process messages in parallel, if any error occurs, it will be handled by the error handling in process_and_delete_message
            tasks = [
                process_and_delete_message(message, CRITICAL_QUEUE_URL)
                for message in critical_response.get('Messages', [])
            ]
            await asyncio.gather(*tasks)
            # continue to the next iteration
            continue

        logging.info("No critical messages found, checking non-critical queue...")
        non_critical_response = sqs_client.receive_message(
            QueueUrl=NON_CRITICAL_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10
        )
        if non_critical_response.get('Messages', []):
            messages = non_critical_response.get('Messages', [])
            tasks = [process_message(message) for message in messages]
            await asyncio.gather(*tasks)
            continue

        logging.info("No non-critical messages found, waiting for 1 second...")
        await asyncio.sleep(1)

async def process_and_delete_message(message, queue_url):
    try:    
        await process_message(message)
        sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=message['ReceiptHandle'])
    except Exception as e:
        logging.error(f"Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(listen_to_sqs_priority())