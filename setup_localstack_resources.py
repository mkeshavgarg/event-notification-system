import boto3
from config import QUEUES, NOTIFICATION_TYPES, PRIORITY_TYPES

# Configure the LocalStack endpoint
localstack_endpoint = "http://localhost:4566"

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch', endpoint_url=localstack_endpoint)
application_autoscaling = boto3.client('application-autoscaling', endpoint_url=localstack_endpoint)


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

def create_user_connections_table():
    dynamodb = boto3.client('dynamodb', endpoint_url=localstack_endpoint)
    table_name = "user_connections"

    try:
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
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
    queue_name = QUEUES["event"]["name"]

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
    queue_name = QUEUES["sms"]["critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

    queue_name = QUEUES["sms"]["non_critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

def create_email_queue():
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    queue_name = QUEUES["email"]["critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")


    queue_name = QUEUES["email"]["non_critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

def create_push_notification_queue():
    sqs = boto3.client('sqs', endpoint_url=localstack_endpoint)
    queue_name = QUEUES["push_notification"]["critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

    queue_name = QUEUES["push_notification"]["non_critical"]["name"]
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    print(f"SQS queue '{queue_name}' created with URL: {queue_url}")

def create_cloudwatch_alarm(queue_name, queue_url):
    """
    Create a CloudWatch alarm for the SQS queue to monitor message count.
    """
    alarm_name = f"{queue_name}_MessageCountAlarm"
    cloudwatch.put_metric_alarm(
        AlarmName=alarm_name,
        MetricName='ApproximateNumberOfMessagesVisible',
        Namespace='AWS/SQS',
        Statistic='Average',
        Period=60,
        EvaluationPeriods=1,
        Threshold=10,  # Example threshold
        ComparisonOperator='GreaterThanThreshold',
        Dimensions=[
            {
                'Name': 'QueueName',
                'Value': queue_name
            }
        ],
        AlarmActions=[
            # Add ARN of the scaling policy or notification target
        ],
        AlarmDescription=f"Alarm when message count in {queue_name} exceeds threshold",
        ActionsEnabled=True
    )
    print(f"CloudWatch alarm '{alarm_name}' created for queue '{queue_name}'.")

def setup_autoscaling_for_queue(queue_name):
    """
    Set up auto-scaling for the SQS queue based on CloudWatch alarms.
    """
    resource_id = f"queue/{queue_name}"
    scalable_dimension = 'sqs:queue:ApproximateNumberOfMessagesVisible'

    # Register the scalable target
    application_autoscaling.register_scalable_target(
        ServiceNamespace='sqs',
        ResourceId=resource_id,
        ScalableDimension=scalable_dimension,
        MinCapacity=1,
        MaxCapacity=10
    )

    # Create a scaling policy
    application_autoscaling.put_scaling_policy(
        PolicyName=f"{queue_name}_ScalingPolicy",
        ServiceNamespace='sqs',
        ResourceId=resource_id,
        ScalableDimension=scalable_dimension,
        PolicyType='TargetTrackingScaling',
        TargetTrackingScalingPolicyConfiguration={
            'TargetValue': 5.0,  # Example target value
            'PredefinedMetricSpecification': {
                'PredefinedMetricType': 'SQSQueueMessagesVisible'
            },
            'ScaleInCooldown': 60,
            'ScaleOutCooldown': 60
        }
    )
    print(f"Auto-scaling setup for queue '{queue_name}'.")

if __name__ == "__main__":
    # Create DynamoDB table
    create_dynamodb_table()

    # Create SNS topic
    topic_arn = create_sns_topic()

    # Create SQS listener
    create_sqs_listener(topic_arn)

    # Create SMS queues
    create_sms_queues()

    # Create email queue
    create_email_queue()

    # Create push notification queue
    create_push_notification_queue()

    # Set up CloudWatch alarms and auto-scaling for all queues
    create_cloudwatch_alarm(QUEUES["event"]["name"], QUEUES["event"]["url"])
    setup_autoscaling_for_queue(QUEUES["event"]["name"])

    # Set up CloudWatch alarms and auto-scaling for all notification queues
    for notification_type in NOTIFICATION_TYPES:
        for priority in PRIORITY_TYPES:
            queue_name = QUEUES[notification_type][priority]["name"]
            queue_url = QUEUES[notification_type][priority]["url"]
            create_cloudwatch_alarm(queue_name, queue_url)
            setup_autoscaling_for_queue(queue_name)
