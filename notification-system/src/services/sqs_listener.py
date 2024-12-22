import boto3
import json
from datetime import datetime
from src.models.event import EventStatus, EventPayload
from src.models.event_types import EventType
from src.models.user_types import UserType
from src.config.settings import QUEUES, LOCALSTACK_ENDPOINT
import uuid
from typing import Dict
from ..config.telemetry import setup_service_telemetry
import time

# Initialize AWS clients
sqs_client = boto3.client('sqs', endpoint_url=LOCALSTACK_ENDPOINT)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=LOCALSTACK_ENDPOINT)
dynamodb_table = dynamodb_client.Table('event')

# Get metrics for SQS listener service
metrics = setup_service_telemetry(service_name="sqs-listener")

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

def get_user_preferences(user_id: str) -> Dict:
    """
    Retrieves user notification preferences from DynamoDB.
    Returns default preferences if none found.
    """
    try:
        # Get user preferences from DynamoDB
        user_prefs_table = dynamodb_client.Table('user_preferences')
        response = user_prefs_table.get_item(
            Key={'user_id': user_id}
        )
        
        if 'Item' in response:
            return response['Item'].get('notification_preferences', {})
        
        # Return default preferences if none found
        return {
            'sms': True,
            'email': True,
            'push': True,
            'quiet_hours': {
                'enabled': False,
                'start': '22:00',
                'end': '08:00'
            },
            'priority_only': False
        }
    except Exception as e:
        print(f"Error fetching user preferences: {e}")
        # Fallback to all notifications enabled
        return {'sms': True, 'email': True, 'push': True}

def route_to_notification_queues(event_payload):
    """
    Routes event to appropriate notification queues based on configuration, priority, and user preferences.
    """
    is_critical = determine_priority(event_payload)
    user_id = event_payload.get('user_id')
    
    # Get user preferences
    user_prefs = get_user_preferences(user_id)
    
    # Check quiet hours if enabled
    if user_prefs.get('quiet_hours', {}).get('enabled', False):
        current_time = datetime.now().strftime('%H:%M')
        quiet_start = user_prefs['quiet_hours']['start']
        quiet_end = user_prefs['quiet_hours']['end']
        
        is_quiet_hours = (quiet_start <= current_time <= quiet_end)
        if is_quiet_hours and not is_critical:
            print(f"Skipping non-critical notification during quiet hours for user {user_id}")
            return

    # Check priority_only setting
    if user_prefs.get('priority_only', False) and not is_critical:
        print(f"Skipping non-critical notification for priority-only user {user_id}")
        return
    
    # Convert payload to string for SQS
    message_body = json.dumps({'Message': json.dumps(event_payload)})
    
    # Route to SMS queues if enabled for user
    if user_prefs.get('sms', False):
        queue_url = QUEUES['sms']['critical']['url'] if is_critical else QUEUES['sms']['non_critical']['url']
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        print(f"Routed to SMS queue: {queue_url}")
    
    # Route to email queues if enabled for user
    if user_prefs.get('email', False):
        queue_url = QUEUES['email']['critical']['url'] if is_critical else QUEUES['email']['non_critical']['url']
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        print(f"Routed to email queue: {queue_url}")
    
    # Route to push notification queue if enabled for user
    if user_prefs.get('push', False):
        queue_url = QUEUES['push_notification']['critical']['url'] if is_critical else QUEUES['push_notification']['non_critical']['url']
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
        try:
            response = sqs_client.receive_message(
                QueueUrl=QUEUES['event']['url'],
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20
            )

            messages = response.get('Messages', [])
            
            # Record queue depth
            metrics["queue_depth"].add(len(messages))
            
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
                        QueueUrl=QUEUES['event']['url'],
                        Entries=entries_to_delete
                    )
                except Exception as e:
                    print(f"Error deleting messages in batch: {e}")

        except Exception as e:
            metrics["failed_messages"].add(1, {"error_type": "queue_processing_error"})
            print(f"Error processing queue: {e}")
            continue

def process_message(message):
    """
    Processes a single SQS message and inserts it into the DynamoDB table.

    Args:
        message (dict): The SQS message to process.
    """
    start_time = time.time()
    try:
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

        # Record successful processing
        metrics["processed_messages"].add(1, {
            "type": event.event_type,
            "priority": event.payload.get("priority", "normal")
        })
        
        # Record processing duration
        processing_duration = (time.time() - start_time) * 1000
        metrics["message_processing_duration"].record(
            processing_duration,
            {"type": event.event_type}
        )
        
    except Exception as e:
        # Record failed processing
        metrics["failed_messages"].add(1, {"error_type": str(type(e).__name__)})
        print(f"Error processing message: {e}")
        raise

if __name__ == "__main__":
    listen_to_sqs()