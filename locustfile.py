from locust import HttpUser, task, between

class EventPublisherUser(HttpUser):
    wait_time = between(1, 2)  # Simulate a wait time between requests

    @task
    def publish_event(self):
        # Define the payload for the event
        payload = {
            "event_id": "test_event",
            "user_id": "user_123",
            "event_name": "test_event_name",
            "payload": {"key": "value"}
        }
        # Send a POST request to the publish_event endpoint
        self.client.post("/events/test_event", json=payload) 