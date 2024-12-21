import os
import boto3
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from models import EventPayload  # Assuming you have a similar model for events
from botocore.config import Config
from typing import List
from itertools import islice
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# celery worker or a lambda function can be used to process the events in batches and with async retry logic
# Configure the retry settings
boto_config = Config(
    retries={
        'max_attempts': 3,  # Maximum number of retry attempts
        'mode': 'standard'  # Retry mode: 'standard' or 'adaptive'
    }
)

# Initialize AWS clients
sns_client = boto3.client('sns', endpoint_url="http://localhost:4566", config=boto_config)
dynamodb_client = boto3.resource('dynamodb', endpoint_url="http://localhost:4566")
dynamodb_table = dynamodb_client.Table('event')

# SNS topic ARN
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:000000000000:event"

def chunked_iterable(iterable, size):
    """Yield successive n-sized chunks from iterable."""
    it = iter(iterable)
    return iter(lambda: tuple(islice(it, size)), ())

def publish_to_sns(payload: dict):
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=str(payload),
            Subject="Event"
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {payload}. Error: {str(e)}")
        # Optionally, send the payload to a DLQ or take other actions

@app.get("/")
def home(request: Request) -> dict[str, str]:
    """
    Home route that provides the URL to access the Swagger UI.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        dict[str, str]: A message with the URL to the Swagger UI.
    """
    url: str = str(request.base_url)
    return {
        "message": f"Navigate to the following URL to access the Swagger UI: {url}docs"
    }

@app.post("/publish_events")
async def publish_events(payloads: List[dict], background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    Publishes a list of events to the SNS topic in batches asynchronously.

    Args:
        payloads (List[dict]): A list of event payloads.
        client side buffering can be used to batch the payloads before sending to the API
        background_tasks (BackgroundTasks): FastAPI background task manager.

    Returns:
        dict[str, str]: A result message indicating the request was received.
    """
    def publish_to_sns_batch(batch: List[dict]):
        for payload in batch:
            publish_to_sns(payload)

    # Process payloads in chunks of 10
    for batch in chunked_iterable(payloads, 10):
        background_tasks.add_task(publish_to_sns_batch, batch)

    return {"result": f"{len(payloads)} events received and will be processed in batches."}

@app.get("/events")
def fetch_events(filter_key: str, filter_value: str) -> dict[str, list[EventPayload]]:
    """
    Fetches events from DynamoDB based on a filter.

    Args:
        filter_key (str): The key to filter events by.
        filter_value (str): The value to filter events by.

    Returns:
        dict[str, list[EventPayload]]: A list of events matching the filter.
    """
    try:
        response = dynamodb_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr(filter_key).eq(filter_value)
        )
        events = response.get('Items', [])
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events/{event_id}")
def get_event(event_id: str) -> dict[str, dict]:
    """
    Retrieves details of a specific event by event_id.

    Args:
        event_id (str): The unique identifier of the event.

    Returns:
        dict[str, dict]: The details of the event.
    """
    try:
        response = dynamodb_table.get_item(Key={'event_id': event_id})
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Event not found.")
        return {"event": response['Item']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

