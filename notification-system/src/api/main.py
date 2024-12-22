import os
import boto3
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from botocore.config import Config
from typing import List, Dict
from itertools import islice

# Use relative imports
from ..models.event import EventPayload, EventStatus
from ..utils.logging import setup_logging
from ..config.settings import (
    SNS_TOPIC_ARN,
    LOCALSTACK_ENDPOINT,
    DYNAMODB_TABLE_NAME
)

app = FastAPI(
    title="Notification System API",
    description="Event-driven notification system for handling multi-channel notifications",
    version="1.0.0"
)

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

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

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
        logger.info(f"Event published to SNS: {payload.get('event_id')}")
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
        payloads (List[dict]): A list of event payloads. Client side buffering can be used to batch the payloads before sending to the API.
        background_tasks (BackgroundTasks): FastAPI background task manager.

    Returns:
        dict[str, str]: A result message indicating the request was received.
    """
    async def publish_to_sns_batch(batch: List[dict]):
        for payload in batch:
            await publish_to_sns(payload)

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
    
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    Establishes WebSocket connection for push notifications.
    """
    try:
        await websocket.accept()
        active_connections[user_id] = websocket
        logger.info(f"WebSocket connection established for user: {user_id}")
        
        # Store connection info in DynamoDB
        connection_info = {
            'user_id': user_id,
            'connection_time': str(datetime.utcnow()),
            'client_type': 'web'
        }
        dynamodb_table.put_item(Item=connection_info)
        
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "status": "received",
                    "message": data
                })
                
        except WebSocketDisconnect:
            # Clean up on disconnect
            if user_id in active_connections:
                del active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")
            
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if user_id in active_connections:
            del active_connections[user_id]
        await websocket.close()

async def notify_client(user_id: str, message: dict):
    """Send notification to a specific client"""
    if user_id in active_connections:
        try:
            websocket = active_connections[user_id]
            await websocket.send_json(message)
            logger.info(f"Notification sent to user: {user_id}")
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {str(e)}")
            if user_id in active_connections:
                del active_connections[user_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

