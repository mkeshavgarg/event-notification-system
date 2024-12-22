import boto3
import json
import asyncio
import aiohttp
import logging
from ..models.event import EventStatus
from aioapns import APNs, NotificationRequest, PushType
from datetime import datetime


# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
dynamodb_client = boto3.resource('dynamodb', endpoint_url=localstack_endpoint)
connections_table = dynamodb_client.Table('user_connections')

# Apple Push Notification Service credentials
APNS_KEY_ID = 'your_key_id'
APNS_TEAM_ID = 'your_team_id'
APNS_AUTH_KEY_PATH = 'path/to/AuthKey.p8'
APNS_TOPIC = 'your.app.bundle.id'

# Configure logging
logging.basicConfig(level=logging.INFO)

async def send_ios_push(device_token, message):
    """
    Sends push notification to iOS devices using APNs
    """
    try:
        # Initialize APNs client with key file
        apns = APNs(
            key=APNS_AUTH_KEY_PATH,
            key_id=APNS_KEY_ID,
            team_id=APNS_TEAM_ID,
            topic=APNS_TOPIC,
            use_sandbox=False
        )
        
        # Create notification request
        notification = NotificationRequest(
            device_token=device_token,
            message={
                "aps": {
                    "alert": message,
                    "sound": "default",
                    "badge": 1
                }
            }
        )
        
        # Send the notification
        await apns.send_notification(notification)
        return EventStatus.SUCCESS
    except Exception as e:
        logging.error(f"Error sending iOS push: {e}")
        raise

async def send_web_push(websocket_id, message):
    """
    Sends push notification to web browser via WebSocket
    """
    try:
        # Get WebSocket connection URL from DynamoDB
        response = connections_table.get_item(
            Key={'websocket_id': websocket_id}
        )
        
        if 'Item' not in response:
            raise Exception(f"No WebSocket connection found for ID: {websocket_id}")
            
        connection_url = response['Item']['connection_url']
        
        # Send message through WebSocket
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(connection_url) as ws:
                await ws.send_json({
                    'type': 'push_notification',
                    'message': message
                })
                
        return EventStatus.SUCCESS
    except Exception as e:
        logging.error(f"Error sending web push: {e}")
        raise

async def get_user_connections(user_id):
    """
    Gets all active connections for a user from DynamoDB
    """
    try:
        response = connections_table.query(
            IndexName='user_id-index',
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        return response.get('Items', [])
    except Exception as e:
        logging.error(f"Error getting user connections: {e}")
        return []

async def send_push_notification(user_id, message):
    """
    Sends push notifications to all user's devices
    """
    connections = await get_user_connections(user_id)
    
    for conn in connections:
        try:
            if conn['device_type'] == 'ios':
                await send_ios_push(conn['device_token'], message)
                logging.info(f"iOS push sent to device: {conn['device_token']}")
                
            elif conn['device_type'] == 'web':
                await send_web_push(conn['websocket_id'], message)
                logging.info(f"Web push sent to websocket: {conn['websocket_id']}")
                
        except Exception as e:
            logging.error(f"Failed to send push to {conn['device_type']}: {e}")
            continue

async def store_connection(user_id, device_type, connection_info):
    """
    Stores new device connection in DynamoDB
    """
    try:
        item = {
            'user_id': user_id,
            'device_type': device_type,
            'created_at': int(datetime.now().timestamp())
        }
        
        if device_type == 'ios':
            item['device_token'] = connection_info
        elif device_type == 'web':
            item['websocket_id'] = connection_info['websocket_id']
            item['connection_url'] = connection_info['connection_url']
            
        connections_table.put_item(Item=item)
        logging.info(f"Stored new {device_type} connection for user {user_id}")
        
    except Exception as e:
        logging.error(f"Failed to store connection: {e}")
        raise
