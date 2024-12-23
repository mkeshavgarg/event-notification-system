import os
import boto3
import uuid
import uvicorn
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from botocore.config import Config
from typing import List, Dict
from itertools import islice
import time

# Use relative imports
from ..models.event import EventPayload
from ..utils.logging import setup_logging
from ..services.push_service import store_connection
from ..config.settings import (
    SNS_TOPIC_ARN,
    LOCALSTACK_ENDPOINT,
    DYNAMODB_TABLE_NAME
)
from ..config.telemetry import setup_telemetry

app = FastAPI(
    title="Notification System API",
    description="Event-driven notification system for handling multi-channel notifications",
    version="1.0.0"
)

# Setup telemetry
metrics = setup_telemetry(app)

# Configure retry settings
boto_config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'standard'
    }
)

# Initialize AWS clients
sns_client = boto3.client('sns', endpoint_url=LOCALSTACK_ENDPOINT, config=boto_config)
dynamodb_client = boto3.resource('dynamodb', endpoint_url=LOCALSTACK_ENDPOINT)
dynamodb_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)

# Setup logging
logger = setup_logging()

def chunked_iterable(iterable, size):
    """Yield successive n-sized chunks from iterable."""
    it = iter(iterable)
    return iter(lambda: tuple(islice(it, size)), ())

async def publish_to_sns(payload: dict):
    """Publish event to SNS with proper error handling"""
    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(payload),  # Properly serialize the payload
            MessageAttributes={
                'event_type': {
                    'DataType': 'String',
                    'StringValue': payload.get('event_type', 'UNKNOWN')
                },
                'priority': {
                    'DataType': 'String',
                    'StringValue': payload.get('payload', {}).get('priority', 'non_critical')
                }
            }
        )
        logger.info(f"Event published to SNS: {payload.get('event_type')}")
        return response
    except Exception as e:
        logger.error(f"Failed to publish event: {payload}. Error: {str(e)}")
        raise

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

    Key Considerations for Scalability and Resilience:
    1. Batch Processing: Processes payloads in chunks of 10 to reduce SNS requests and manage load.
    2. Asynchronous Execution: Uses FastAPI's BackgroundTasks for non-blocking SNS publishing.
    3. Retry Logic: Configured with boto3's retry strategy to handle transient errors automatically.
    4. Error Handling: Logs errors with detailed messages for diagnostics and prevents application crashes.
    5. Scalability: Leverages AWS SNS's inherent scalability and FastAPI's concurrency capabilities.

    Args:
        payloads (List[dict]): A list of event payloads. Client side buffering can be used to batch the payloads.
        background_tasks (BackgroundTasks): FastAPI background task manager.

    Returns:
        dict[str, str]: A result message indicating the request was received.
    """
    try:
        batch_count = 0
        start_time = time.time()
        
        async def publish_to_sns_batch(batch: List[dict]):
            for payload in batch:
                try:
                    await publish_to_sns(payload)
                    # Record individual notification metrics
                    metrics["notification_counter"].add(1, {
                        "type": payload.get('event_type', 'UNKNOWN'),
                        "priority": payload.get('payload', {}).get('priority', 'non_critical')
                    })
                except Exception as e:
                    logger.error(f"Failed to publish event in batch: {str(e)}")
                    # You might want to add error metrics here
                    continue

        # Process payloads in chunks of 10
        for batch in chunked_iterable(payloads, 10):
            background_tasks.add_task(publish_to_sns_batch, batch)
            batch_count += 1

        # Convert processing_duration to string to match response type
        processing_duration = str(round((time.time() - start_time) * 1000, 2))
        metrics["notification_duration"].record(
            float(processing_duration),  # Convert back to float for metrics
            {"batch_size": str(len(payloads)), "batch_count": str(batch_count)}
        )
        logger.info(f"processing_duration: {processing_duration}")
        return {
            "result": f"{len(payloads)} events received and will be processed in {batch_count} batches.",
            "processing_time_ms": processing_duration  # Now returns string
        }
    except Exception as e:
        logger.error(f"Error in batch event publishing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket):
    """
    Establishes WebSocket connection for push notifications.
    """
    # TODO: get user_id from the request headers or from the database 
    user_id = "123123"
    try:
        await websocket.accept()
        await store_connection(user_id, 'web', {'websocket_id': websocket.client.host, 'connection_url': str(websocket.client.url)})
        logger.info(f"WebSocket connection established for user: {user_id}")
        
        # push notification service is listening to the SQS queue and will send the notification to the client using the websocket_id stored in the database
            
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        await delete_connection(user_id, 'web')
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

