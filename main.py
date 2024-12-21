import os
import boto3
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from models import EventPayload  # Assuming you have a similar model for events

app = FastAPI()

# Initialize AWS clients
sns_client = boto3.client('sns', endpoint_url="http://localhost:4566")
dynamodb_client = boto3.resource('dynamodb', endpoint_url="http://localhost:4566")
dynamodb_table = dynamodb_client.Table('event')

# SNS topic ARN
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:000000000000:event"

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

@app.post("/events/{event_name}")
async def publish_event(event_name: str, payload: dict, background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    Publishes an event to the SNS topic asynchronously.

    Args:
        event_name (str): The name of the event.
        payload (dict): The payload of the event.
        background_tasks (BackgroundTasks): FastAPI background task manager.

    Returns:
        dict[str, str]: A result message indicating the request was received.
    """
    def publish_to_sns(event_name: str, payload: dict):
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=str(payload),
            Subject=event_name
        )

    background_tasks.add_task(publish_to_sns, event_name, payload)
    return {"result": f"Event '{event_name}' received and will be processed."}

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
