import boto3
import json
import asyncio
import aiohttp
import logging
from models import EventStatus

# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=localstack_endpoint)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=localstack_endpoint)
dynamodb_table = dynamodb_client.Table('event')

# SQS queue URLs
CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_critical"
NON_CRITICAL_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_non_critical"

DLQ_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/dlq"

# SendGrid API key
SENDGRID_API_KEY = 'your_sendgrid_api_key'

# Configure logging
logging.basicConfig(level=logging.INFO)

async def send_email(to_email, subject, content):
    """
    Sends an email using SendGrid.
    """
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": "your_email@example.com"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": content}]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status != 202:
                raise Exception(f"Failed to send email: {response.status}")
            return EventStatus.SUCCESS

async def process_message(message):
    """
    Processes a single SQS message and sends an email notification.
    """
    body = json.loads(message['Body'])
    event_payload = json.loads(body['Message'])

    to_email = event_payload.get('user_email', 'default@example.com')
    subject = "Event Notification"
    content = f"Event {event_payload.get('event_name', 'unknown')} occurred."

    retry_count = event_payload.get('retry_count_email', 0)
    max_retries = 5
    backoff_factor = 2

    event_id = event_payload.get('event_id')

    while retry_count < max_retries:
        try:
            status = await send_email(to_email, subject, content)
            logging.info(f"Email sent to {to_email}")
            if status == EventStatus.SUCCESS:
                # Update DynamoDB with success status
                dynamodb_table.update_item(
                    Key={'event_id': event_id},
                    UpdateExpression='SET #status = :status',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={':status': EventStatus.SUCCESS}
                )
            return
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            retry_count += 1
            
            # Update retry count in DynamoDB
            dynamodb_table.update_item(
                Key={'event_id': event_id},
                UpdateExpression='SET retry_count_email = :retry_count',
                ExpressionAttributeValues={':retry_count': retry_count}
            )
            await asyncio.sleep(backoff_factor ** retry_count)

    # If all retries fail, send the message to the DLQ
    logging.error(f"Failed to send email after {max_retries} retries, sending to DLQ")
    event_payload['retry_count_email'] = retry_count
    
    # Update DynamoDB with failed status
    dynamodb_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': EventStatus.FAILED}
    )
    
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