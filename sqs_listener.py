import boto3
import json
from datetime import datetime
from models import EventStatus, EventPayload
from event_types import EventType
from user_types import UserType
import uuid
# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=localstack_endpoint)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=localstack_endpoint)
dynamodb_table = dynamodb_client.Table('event')

# SQS queue URLs
EVENT_QUEUE_URL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/event_queue"

# Notification queue URLs
SMS_CRITICAL_QUEUE = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_critical"
SMS_NON_CRITICAL_QUEUE = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_non_critical"

EMAIL_CRITICAL_QUEUE = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_critical"
EMAIL_NON_CRITICAL_QUEUE = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_non_critical"

PUSH_NOTIFICATION_QUEUE = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_queue_critical"
PUSH_NOTIFICATION_QUEUE_NON_CRITICAL = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_queue_non_critical"

def determine_priority(event_payload):
    """
    Determines if an event is critical based on event attributes.
    """
    # Example priority logic - customize based on your needs
    critical_events = [EventType.MENTION, EventType.COMMENT, EventType.REPLY]
    critical_user_types = [UserType.ADMIN, UserType.PREMIUM]
    # business logic to determine if an event is critical,
    # TODO: add more logic here, for example, if the event is a mention, then it is critical
    is_critical = (
        event_payload.get('event_type', '').lower() in critical_events or
        event_payload.get('priority', '').lower() == 'high' or
        event_payload.get('user_type', '').lower() in critical_user_types # TODO: add user type to event payload
    )
    
    return is_critical

def route_to_notification_queues(event_payload):
    """
    Routes event to appropriate notification queues based on configuration and priority.
    """
    is_critical = determine_priority(event_payload)
    notification_config = event_payload.get('notifications', {})
    
    # Convert payload to string for SQS
    message_body = json.dumps({'Message': json.dumps(event_payload)})
    
    # Route to SMS queues
    if notification_config.get('sms', False):
        queue_url = SMS_CRITICAL_QUEUE if is_critical else SMS_NON_CRITICAL_QUEUE
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        print(f"Routed to SMS queue: {queue_url}")
    
    # Route to email queues
    if notification_config.get('email', False):
        queue_url = EMAIL_CRITICAL_QUEUE if is_critical else EMAIL_NON_CRITICAL_QUEUE
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        print(f"Routed to email queue: {queue_url}")
    
    # Route to push notification queue
    if notification_config.get('push', False):
        queue_url = PUSH_NOTIFICATION_QUEUE if is_critical else PUSH_NOTIFICATION_QUEUE_NON_CRITICAL
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        print(f"Routed to push notification queue: {queue_url}")

def listen_to_sqs():
    """
    Continuously listens to the SQS queue and processes messages in batches.
    """
    while True:
        # Receive messages from the SQS queue in batches
        print("Listening to SQS queue...")
        response = sqs_client.receive_message(
            QueueUrl=EVENT_QUEUE_URL,
            MaxNumberOfMessages=10,  # Increased to process up to 10 messages at once
            WaitTimeSeconds=20  # Increased wait time since we're processing in batches
        )

        messages = response.get('Messages', [])
        if not messages:
            continue

        # Process messages in batch
        entries_to_delete = []
        for message in messages:
            try:
                # Process the message
                process_message(message)

                # Add message to deletion batch
                entries_to_delete.append({
                    'Id': message['MessageId'],
                    'ReceiptHandle': message['ReceiptHandle']
                })
            except Exception as e:
                print(f"Error processing message: {e}")

        # Delete processed messages in batch
        if entries_to_delete:
            try:
                sqs_client.delete_message_batch(
                    QueueUrl=EVENT_QUEUE_URL,
                    Entries=entries_to_delete
                )
            except Exception as e:
                print(f"Error deleting messages in batch: {e}")

def process_message(message):
    """
    Processes a single SQS message and inserts it into the DynamoDB table.

    Args:
        message (dict): The SQS message to process.
    """
    # Parse the message body
    body = json.loads(message['Body'])
    event_payload = json.loads(body['Message'])

    event_id = str(uuid.uuid4())
    # Create an event entry with status START
    event = EventPayload(
        event_id=event_id,
        status=EventStatus.START,
        retry_count_sms=event_payload.get('retry_count_sms', 0),
        retry_count_email=event_payload.get('retry_count_email', 0),
        retry_count_push=event_payload.get('retry_count_push', 0),
        user_id=event_payload.get('user_id', 'unknown'),
        event_type=event_payload.get('event_type', EventType.UNKNOWN),
        payload={
            "parent_id": event_payload.get('parent_id', 'unknown'),
            "parent_type": event_payload.get('parent_type', 'unknown'),
            "timestamp": event_payload.get('timestamp', datetime.now().isoformat()),
            "priority": event_payload.get('priority', 'normal')
        }
    )

    # Insert the event into the DynamoDB table
    print(event.model_dump())
    dynamodb_table.put_item(Item=event.model_dump())
    print(f"Inserted event into DynamoDB: {event}")

    # Route to notification queues
    route_to_notification_queues(event_payload)

if __name__ == "__main__":
    listen_to_sqs()