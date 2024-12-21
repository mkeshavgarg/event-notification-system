import boto3

# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Create a DynamoDB table
def create_dynamodb_table():
    dynamodb = boto3.client('dynamodb', endpoint_url=localstack_endpoint)
    table_name = "event"

    try:
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'event_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'status',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'event_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'status',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'retry_count_email',
                    'AttributeType': 'N'
                },
                {
                    'AttributeName': 'retry_count_sms',
                    'AttributeType': 'N'
                },
                {
                    'AttributeName': 'retry_count_push',
                    'AttributeType': 'N'
                },
                {
                    'AttributeName': 'payload',
                    'AttributeType': 'M'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'event_type',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table_status = response['TableDescription']['TableStatus']
        print("Table status:", table_status)
    except Exception as e:
        print(f"Error creating table: {e}")

# Create an SNS topic
def create_sns_topic():
    sns = boto3.client('sns', endpoint_url=localstack_endpoint)
    topic_name = "event"

    response = sns.create_topic(Name=topic_name)
    topic_arn = response['TopicArn']
    print(f"SNS topic '{topic_name}' created with ARN: {topic_arn}")
    return topic_arn

# Create an SQS queue and subscribe it to the SNS topic
def create_sqs_listener(topic_arn):
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    sns = boto3.client('sns', endpoint_url=localstack_endpoint)
    queue_name = "event_queue"

    # Create SQS queue
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

    # Get the queue ARN
    response = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['QueueArn']
    )
    queue_arn = response['Attributes']['QueueArn']

    # Subscribe the SQS queue to the SNS topic
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol='sqs',
        Endpoint=queue_arn
    )
    print(f"SQS queue '{queue_name}' subscribed to SNS topic '{topic_arn}'.")

def create_sms_queues():
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    queue_name = "sms_queue_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

    queue_name = "sms_queue_non_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

def create_email_queue():
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    queue_name = "email_queue_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")


    queue_name = "email_queue_non_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

def create_push_notification_queue():
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    queue_name = "push_notification_queue_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

    queue_name = "push_notification_queue_non_critical"
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

if __name__ == "__main__":
    create_dynamodb_table()
    topic_arn = create_sns_topic()
    create_sqs_listener(topic_arn)
    create_sms_queues()
    create_email_queue()
    create_push_notification_queue()