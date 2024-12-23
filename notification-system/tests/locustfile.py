from locust import HttpUser, task, between
from datetime import datetime
class EventPublisherUser(HttpUser):
    wait_time = between(1, 2)  # Simulate a wait time between requests

    @task
    def publish_event(self):
        # Define the payload for the event
        payload = {
            "parent_id": "post_67890",
            "parent_type": "post", 
            "user_id": "user_123",
            "event_type": "LIKE",
            "timestamp": datetime.now().isoformat(),
            "priority": "critical"
        }
        # Send a POST request to the publish_event endpoint
        self.client.post("/publish_events", json=[payload]) 