import boto3
import json
import asyncio
import aiohttp
import logging

# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=localstack_endpoint)

# SQS queue URLs
QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_queue"
DLQ_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/dlq"

# Push Notification Service API credentials
PUSH_API_URL = 'https://api.pushservice.com/send'
PUSH_API_KEY = 'your_push_service_api_key'

# Configure logging
logging.basicConfig(level=logging.INFO)

async def send_push_notification(client_id, message):
    """
    Sends a push notification using a hypothetical push notification service.
    """
    headers = {
        "Authorization": f"Bearer {PUSH_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "client_id": client_id,
        "message": message
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(PUSH_API_URL, headers=headers, json=data) as response:
            if response.status != 200:
                raise Exception(f"Failed to send push notification: {response.status}")

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

    target_clients = apply_business_logic(event_payload)
    notification_message = f"Event {event_payload.get('event_name', 'unknown')} occurred."

    for client_id in target_clients:
        try:
            await send_push_notification(client_id, notification_message)
            logging.info(f"Push notification sent to client {client_id}")
        except Exception as e:
            logging.error(f"Error sending push notification to client {client_id}: {e}")
            # Optionally, handle retries or log to a DLQ

async def listen_to_sqs():
    """
    Continuously listens to the SQS queue and processes messages.
    """
    while True:
        logging.info("Listening to SQS queue...")
        response = sqs_client.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10
        )

        messages = response.get('Messages', [])
        for message in messages:
            try:
                await process_message(message)
                sqs_client.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
            except Exception as e:
                logging.error(f"Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(listen_to_sqs())