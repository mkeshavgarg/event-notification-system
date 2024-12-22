# Event-Driven Notification System

A resilient and scalable event-driven notification system built with Python that handles notifications for social media platforms, supporting push notifications, emails, and SMS alerts based on user activities.

## Architecture Overview

The system is built on a microservices architecture, leveraging AWS services for scalability and resilience:

```
notification-system/
├── src/
│   ├── api/              # FastAPI application endpoints
│   ├── services/         # Core notification services
│   ├── models/           # Data models and type definitions
│   ├── config/           # Configuration and settings
│   ├── infrastructure/   # AWS/LocalStack setup
│   └── utils/            # Shared utilities
├── tests/                # Test suite
└── docs/                 # Documentation
```

### Key Components
- **Amazon SQS**: Message queuing and decoupling
- **AWS Lambda/EC2/ECS**: Message processing
- **Amazon DynamoDB**: Metadata and status storage
- **CloudWatch**: Performance monitoring and autoscaling
- **SNS/Third-party APIs**: Notification delivery

## Features

- **Multi-Channel Notifications**
  - Email notifications via SendGrid
  - SMS notifications via Twilio
  - Push notifications via Firebase/APNs
  
- **Priority-Based Processing**
  - Critical and non-critical queues for each channel
  - Priority-based message routing
  - Dead Letter Queue (DLQ) for failed messages

- **Robust Error Handling**
  - Exponential backoff retry mechanism
  - Comprehensive error logging
  - Failed message recovery

- **Scalability**
  - Horizontal scaling with multiple workers
  - Parallel message processing
  - Supervisor-managed processes

## Core Components

### 1. Main Application (`src/api/main.py`)
- Entry point for FastAPI application
- Handles HTTP requests for event publishing
- Provides event status endpoints
- Implements WebSocket connections

### 2. Data Models (`src/models/`)
- `event.py`: Event status and payload definitions
- `event_types.py`: Supported event type enumerations
- `user_types.py`: User role definitions

### 3. Services (`src/services/`)
#### Email Service (`email_service.py`)
- SendGrid integration
- Priority-based email processing
- Retry mechanism with backoff

#### SMS Service (`sms_service.py`)
- Twilio integration
- Critical message prioritization
- Status tracking and updates

#### Push Notification Service (`push_service.py`)
- Firebase/APNs integration
- Device token management
- Platform-specific payload handling

### 4. Infrastructure (`src/infrastructure/`)
- LocalStack resource setup
- Queue creation and configuration
- DynamoDB table management

## System Flow

### Flow Chart
```mermaid
graph LR
    A[Client] -->|POST /event| B[FastAPI]
    B -->|Publish| C[SNS Topic]
    C -->|Fan Out| D[SQS Queues]
    D -->|Critical| E[Priority Queue]
    D -->|Non-Critical| F[Standard Queue]
    E --> G[Notification Services]
    F --> G
    G -->|Email| H[SendGrid]
    G -->|SMS| I[Twilio]
    G -->|Push| J[Firebase/APNs]
    G -->|Status Update| K[DynamoDB]
    H & I & J -.->|Failure| L[DLQ]
```

1. **Event Triggering**
   - User activity triggers event
   - Background tasks publish to SNS

2. **Message Processing**
   - SNS fans out to SQS queues
   - Priority-based routing
   - Batch processing for performance

3. **Notification Delivery**
   - Channel-specific processing
   - Third-party API integration
   - Status tracking in DynamoDB

4. **Error Handling**
   - Retry mechanisms
   - DLQ for failed messages
   - Manual intervention triggers

## API Usage

### Publish Event API

The main entry point for triggering notifications is the `/event` endpoint:

```bash
# Using curl
curl -X POST http://localhost:8000/event \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_12345",
    "event_type": "LIKE",
    "payload": {
      "parent_id": "post_67890",
      "parent_type": "post",
      "timestamp": "2023-10-15T12:34:56Z",
      "priority": "critical"
    }
  }'

# Using Python requests
import requests
requests.post(
    'http://localhost:8000/event',
    json={
        "user_id": "user_12345",
        "event_type": "LIKE",
        "payload": {
            "parent_id": "post_67890",
            "parent_type": "post",
            "timestamp": "2023-10-15T12:34:56Z",
            "priority": "critical"
        }
    }
)
```

### Load Testing with Locust

The repository includes a Locust file for load testing the event publishing API:

```python
# tests/locustfile.py example usage
locust -f tests/locustfile.py --host http://localhost:8000
```

Then visit http://localhost:8089 to access the Locust web interface.

### Event Types

Supported event types for notifications:
- LIKE
- COMMENT
- SHARE
- FOLLOW
- UNFOLLOW
- MENTION
- MESSAGE
- POST

### Response Format

```json
{
    "event_id": "1234567890",
    "status": "SUCCESS",
    "message": "Event published successfully"
}
```

## Local Development Setup

1. **Environment Setup**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **LocalStack Setup**
```bash
# Start LocalStack
localstack start

# Verify services
localstack status services

# Setup resources
python -m src.infrastructure.setup_localstack
```

3. **Start Services**
```bash
# Start supervisor
supervisord -c supervisord.conf

# Check status
supervisorctl status
```

4. **Run API Server**
```bash
uvicorn src.api.main:app --reload --port 8000 --host 0.0.0.0 --workers 3
```

5. **Load Testing**
```bash
# Run Locust tests
locust -f tests/locustfile.py --host http://localhost:8000
```

## Monitoring

- **Service Status**: `supervisorctl status`
- **Logs**: `/tmp/sqs_listener*.log`
- **Metrics**: CloudWatch dashboards
- **Performance**: Locust reports

## Security

See [SECURITY.md](SECURITY.md) for:
- Supported versions
- Security measures
- Vulnerability reporting

## API Documentation

Available at `/docs` when running the server:
- Event publishing
- Status checking
- Subscription management

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Authors

- Initial work - [Your Name]

## Acknowledgments

- FastAPI
- LocalStack
- AWS Services
- SendGrid
- Twilio


