import boto3
import json
import asyncio
import aiohttp
import logging
from botocore.exceptions import ClientError
from models import EventStatus

# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=localstack_endpoint)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=localstack_endpoint)
dynamodb_table = dynamodb_client.Table('sms_events')

# SQS queue URLs
CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_critical"
NON_CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_non_critical" 
DLQ_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/dlq"

# Twilio API credentials
TWILIO_ACCOUNT_SID = 'your_twilio_account_sid'
TWILIO_AUTH_TOKEN = 'your_twilio_auth_token'
TWILIO_PHONE_NUMBER = 'your_twilio_phone_number'

# Configure logging
logging.basicConfig(level=logging.INFO)

async def send_sms(to_number, message):
    """
    Sends an SMS using Twilio.
    """
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth = aiohttp.BasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    data = {
        "From": TWILIO_PHONE_NUMBER,
        "To": to_number,
        "Body": message
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, auth=auth, data=data) as response:
            if response.status != 201:
                raise Exception(f"Failed to send SMS: {response.status}")
            return EventStatus.SUCCESS

async def update_dynamodb_status(message_id, status, retry_count):
    """
    Updates the status and retry count of a message in DynamoDB.
    """
    try:
        dynamodb_table.update_item(
            Key={'message_id': message_id},
            UpdateExpression="SET #s = :status, retry_count = :retry_count",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': status,
                ':retry_count': retry_count
            }
        )
        logging.info(f"Updated DynamoDB for message_id {message_id} with status {status}")
    except ClientError as e:
        logging.error(f"Failed to update DynamoDB: {e}")

async def process_message(message):
    """
    Processes a single SQS message and sends an SMS notification.
    """
    body = json.loads(message['Body'])
    event_payload = json.loads(body['Message'])

    message_id = event_payload.get('message_id')
    to_number = event_payload.get('user_phone', '+1234567890')
    sms_message = f"Event {event_payload.get('event_name', 'unknown')} occurred."

    retry_count = 0
    max_retries = 5
    backoff_factor = 2

    # First update DynamoDB to IN_PROGRESS status
    await update_dynamodb_status(message_id, EventStatus.IN_PROGRESS, retry_count)

    while retry_count < max_retries:
        try:
            # Attempt to send SMS and await the response
            status = await send_sms(to_number, sms_message)
            logging.info(f"SMS sent to {to_number}")
            
            # Only update status after confirmed successful send
            if status == EventStatus.SUCCESS:
                await update_dynamodb_status(message_id, EventStatus.SUCCESS, retry_count)
            return
        except Exception as e:
            logging.error(f"Error sending SMS: {e}")
            retry_count += 1
            await update_dynamodb_status(message_id, EventStatus.RETRY, retry_count)
            await asyncio.sleep(backoff_factor ** retry_count)

    # If all retries fail, send the message to the DLQ
    logging.error(f"Failed to send SMS after {max_retries} retries, sending to DLQ")
    await update_dynamodb_status(message_id, EventStatus.FAILED, retry_count)
    sqs_client.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(event_payload))

async def listen_to_sqs_with_priority():
    """
    Continuously listens to both critical and non-critical SQS queues with priority.
    """
    while True:
        logging.info("Checking critical queue first...")
        # Try critical queue first
        critical_response = sqs_client.receive_message(
            QueueUrl=CRITICAL_QUEUE_URL,
            MaxNumberOfMessages=10,  # Process in batches of 10
            WaitTimeSeconds=5
        )

        critical_messages = critical_response.get('Messages', [])
        if critical_messages:
            logging.info(f"Processing {len(critical_messages)} critical messages")
            for message in critical_messages:
                try:
                    await process_message(message)
                    sqs_client.delete_message(
                        QueueUrl=CRITICAL_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception as e:
                    logging.error(f"Error processing critical message: {e}")
            continue  # Keep processing critical messages if any exist

        # Only check non-critical if no critical messages
        logging.info("Checking non-critical queue...")
        non_critical_response = sqs_client.receive_message(
            QueueUrl=NON_CRITICAL_QUEUE_URL, 
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5
        )

        non_critical_messages = non_critical_response.get('Messages', [])
        if non_critical_messages:
            logging.info(f"Processing {len(non_critical_messages)} non-critical messages")
            for message in non_critical_messages:
                try:
                    await process_message(message)
                    sqs_client.delete_message(
                        QueueUrl=NON_CRITICAL_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception as e:
                    logging.error(f"Error processing non-critical message: {e}")

        # Small delay before next iteration
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(listen_to_sqs_with_priority())