# Resilient and Scalable Event-Driven Notification System

## Overview
This system is designed to handle notifications for a social media platform, sending push notifications, emails, and SMS alerts based on user activities such as likes, comments, and shares. The architecture is event-driven, ensuring scalability and resilience to handle millions of notifications in near real-time.

## Architecture
The system is built on a microservices architecture, leveraging AWS services for scalability and resilience. Key components include:

- **Amazon SQS**: Used for decoupling and buffering messages between services
- **AWS Lambda / EC2 / ECS**: Processes messages and triggers notifications 
- **Amazon DynamoDB**: Stores metadata and status of notifications
- **CloudWatch**: Monitors system performance and triggers autoscaling
- **SNS / Third-party APIs**: Sends notifications via email, SMS, and push notifications

## Components

### 1. Main Application (`main.py`)
Purpose: Acts as the entry point for the FastAPI application, handling incoming HTTP requests to publish events and fetch event data.

Key Functions:
- `home`: Provides a welcome message with a link to the Swagger UI
- `publish_event`: Publishes events to an SNS topic asynchronously using FastAPI's background tasks
- `fetch_events`: Retrieves events from DynamoDB based on a filter
- `get_event`: Fetches details of a specific event by its ID

### 2. Data Models (`models.py`) 
Purpose: Defines the data models used in the application, ensuring data consistency and validation.

Key Classes:
- `EventStatus`: An enumeration of possible event statuses (START, PROCESSING, SUCCESS, FAILED)
- `EventPayload`: A Pydantic model representing the structure of an event

### 3. LocalStack Resource Setup (`setup_localstack_resources.py`)
Purpose: Sets up the necessary AWS resources in LocalStack for local development and testing.

Key Functions:
- `create_dynamodb_table`: Creates a DynamoDB table for event data
- `create_sns_topic`: Creates an SNS topic for publishing events
- `create_sqs_listener`: Creates an SQS queue and subscribes it to the SNS topic
- `create_sms_queues` and `create_email_queue`: Create separate queues for critical/non-critical notifications

### 4. Process Management (`supervisord.conf`)
Purpose: Manages the execution of multiple instances of the SQS listener scripts.

Key Configurations:
- Defines programs for sqs_listener, sqs_listener_email, and sqs_listener_sms
- Configures autostart, autorestart, and multiple processes
- Logs output and errors to specific files

### 5. SQS Listener (`sqs_listener.py`)
Purpose: Listens to the SQS queue and processes messages.

Key Functions:
- `determine_priority`: Determines event criticality
- `route_to_notification_queues`: Routes events based on configuration
- `listen_to_sqs`: Continuously processes messages in batches
- `process_message`: Processes individual messages

### 6. Notification Processors

#### SMS Notifications (`send_sms_notif.py`)
Purpose: Handles SMS notifications via Twilio.

Key Functions:
- `send_sms`: Sends SMS using Twilio's API
- `update_dynamodb_status`: Updates message status
- `process_message`: Implements retry logic
- `listen_to_sqs_with_priority`: Prioritizes critical messages

#### Push Notifications (`send_push_notif.py`) 
Purpose: Handles push notifications.

Key Functions:
- `send_push_notification`: Sends notifications
- `apply_business_logic`: Determines target clients
- `process_message`: Processes and sends notifications

#### Email Notifications (`send_email_notif.py`)
Purpose: Handles email notifications via SendGrid.

Key Functions:
- `send_email`: Sends emails using SendGrid
- `process_message`: Implements retry logic
- `listen_to_sqs_with_priority`: Prioritizes critical messages

## Error Handling and Resilience
- Retry Mechanisms with exponential backoff
- Dead Letter Queue (DLQ) for failed messages
- Idempotency handling

## Scalability
- Horizontal scaling capability
- Decoupled architecture via SQS queues
- Priority queues for critical/non-critical messages

## System Flow
1. User activity triggers event
    backgroound tasks are triggered to publish the event to SNS topic to improve performance
2. Event published to SNS topic
3. SNS fans out to SQS queue
4. SQS listener processes messages in batches to improve performance
5. Business logic is applied to the event
6. Based on criticality, messages are routed to appropriate queues for SMS, Email, and Push Notifications
7. Notifications sent via third-party services
8. Status logged in DynamoDB at every step
9. Failed messages sent to DLQ and manual intervention is required to process them
10. CloudWatch monitors and triggers autoscaling
11. Locust is used to test the system

---

This system provides a robust, scalable solution for handling notifications in a social media platform. Configure service endpoints and credentials according to your environment.

## Local Development Setup

1. Setup Python Environment 
2. Install requirements 
   ```bash
   pip install -r requirements.txt
   ```
3.  Install AWS CLI if not already installed
   ```bash
   pip install awscli-local
   ```
4. Start LocalStack
   ```bash
   # Start LocalStack
   localstack start

   # Verify LocalStack is running
   localstack status services
   ```
5. Run `python setup_localstack_resources.py` to create the necessary resources
6. Run the following commands to start the SQS listener:
   ```bash
   # Install supervisord if not already installed
   pip install supervisor

   # Start supervisord with config
   supervisord -c supervisord.conf

   # Check status
   supervisorctl status
   ```
   This will start the SQS listener as a background process that automatically restarts if it fails.
7. Run main.py to start the FastAPI application
   ```bash
   uvicorn main:app --reload --port 8000 --host 0.0.0.0 --workers 3 
   ```
8. Run the following commands to test the system with Locust:
   ```bash
   # Install locust if not already installed
   pip install locust

   # Create a locustfile.py with test scenarios
   # Run locust
   locust -f locustfile.py --host http://localhost:8000

   # Access the Locust web interface at http://localhost:8089
   # Configure number of users and spawn rate
   # Start the test and monitor results
   ```


