import os
import boto3
import uuid
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from models import EventPayload  # Assuming you have a similar model for events
from botocore.config import Config
from typing import List
from itertools import islice
import logging
from push_notif_service import store_connection
from config import SNS_TOPIC_ARN
from fastapi_websocket_pubsub import PubSubEndpoint
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
    
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Establishes WebSocket connection for push notifications.
    
    Args:
        websocket (WebSocket): The WebSocket connection object
        user_id (str): ID of the user connecting
    """
    user_id = "123"
    try:
        await websocket.accept()
        
        # Generate unique websocket ID
        websocket_id = str(uuid.uuid4())
        
        # Store connection info in DynamoDB
        connection_info = {
            'websocket_id': websocket_id,
            'connection_url': str(websocket.url)
        }
        await store_connection(user_id, 'web', connection_info)
        
        try:
            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Message received: {data}")
                
        except WebSocketDisconnect:
            # Clean up connection info from DynamoDB on disconnect
            logging.info(f"WebSocket disconnected for user {user_id}")
            
    except Exception as e:
        logging.error(f"Error in WebSocket connection: {e}")
        await websocket.close()


