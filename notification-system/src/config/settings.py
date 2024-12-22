QUEUES = {
    "event": {
        "name": "event_queue",
        "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/event_queue"
    },
    "sms": {
        "critical": {
            "name": "sms_queue_critical",
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_critical"
        },
        "non_critical": {
            "name": "sms_queue_non_critical", 
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/sms_queue_non_critical"
        }
    },
    "email": {
        "critical": {
            "name": "email_queue_critical",
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_critical"
        },
        "non_critical": {
            "name": "email_queue_non_critical",
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/email_queue_non_critical"
        }
    },
    "push_notification": {
        "critical": {
            "name": "push_notification_queue_critical",
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_queue_critical"
        },
        "non_critical": {
            "name": "push_notification_queue_non_critical",
            "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/push_notification_queue_non_critical"
        }
    },
    "dlq": {
        "name": "dlq",
        "url": "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/dlq"
    }
}

SNS_TOPIC_NAME = "event"
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:000000000000:event"

NOTIFICATION_TYPES = ["sms", "email", "push_notification"]

# TODO: add more priority types
PRIORITY_TYPES = ["critical", "non_critical"]

LOCALSTACK_ENDPOINT = "http://localhost:4566"

DYNAMODB_TABLE_NAME = "event"

WEBSOCKET_TABLE_NAME = "websocket_connections"
