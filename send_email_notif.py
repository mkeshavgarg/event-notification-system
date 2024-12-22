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

    # First update DynamoDB to IN_PROGRESS status
    dynamodb_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': EventStatus.IN_PROGRESS}
    )

    while retry_count < max_retries:
        try:
            # Attempt to send email and await the response
            status = await send_email(to_email, subject, content)
            logging.info(f"Email sent to {to_email}")
            
            # Only update status after confirmed successful send
            if status == EventStatus.SUCCESS:
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
            
            if retry_count < max_retries:
                await asyncio.sleep(backoff_factor ** retry_count)

    # Only update FAILED status after all retries are exhausted
    logging.error(f"Failed to send email after {max_retries} retries, sending to DLQ")
    event_payload['retry_count_email'] = retry_count
    
    # Update DynamoDB with failed status
    dynamodb_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': EventStatus.FAILED}
    )
    
    # Send to DLQ
    sqs_client.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(event_payload))

async def listen_to_sqs_with_priority():
    """
    Continuously listens to both critical and non-critical SQS queues with priority,
    processing messages in parallel within each batch.
    """
    while True:
        # Try critical queue first
        critical_response = sqs_client.receive_message(
            QueueUrl=CRITICAL_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5
        )

        critical_messages = critical_response.get('Messages', [])
        if critical_messages:
            logging.info(f"Processing {len(critical_messages)} critical messages in parallel")
            # Process messages in parallel, if any error occurs, it will be handled by the error handling in process_and_delete_message
            tasks = [
                process_and_delete_message(message, CRITICAL_QUEUE_URL)
                for message in critical_messages
            ]
            await asyncio.gather(*tasks)
            continue

        # Only check non-critical if no critical messages
        non_critical_response = sqs_client.receive_message(
            QueueUrl=NON_CRITICAL_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5
        )

        non_critical_messages = non_critical_response.get('Messages', [])
        if non_critical_messages:
            logging.info(f"Processing {len(non_critical_messages)} non-critical messages in parallel")
            tasks = [
                process_and_delete_message(message, NON_CRITICAL_QUEUE_URL)
                for message in non_critical_messages
            ]
            # Process messages in parallel, if any error occurs, it will be handled by the error handling in process_and_delete_message
            await asyncio.gather(*tasks)

        await asyncio.sleep(1)

async def process_and_delete_message(message, queue_url):
    """
    Process a message and delete it from the queue if successful.
    """
    try:
        await process_message(message)
        sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )
    except Exception as e:
        logging.error(f"Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(listen_to_sqs_with_priority())