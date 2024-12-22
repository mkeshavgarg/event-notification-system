from typing import Optional, Dict
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class EventStatus(str, Enum):
    START = "START"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class EventPayload(BaseModel):
    event_id: Optional[str]
    status: EventStatus
    retry_count_email: int = 0
    retry_count_sms: int = 0
    retry_count_push: int = 0
    user_id: str
    event_type: str
    payload: Dict[str, Optional[str]]

    class Config:
        schema_extra = {
            "example": {
                "event_id": "1234567890",
                "status": "START",
                "retry_count_email": 0,
                "retry_count_sms": 0,
                "retry_count_push": 0,
                "user_id": "user_12345",
                "event_type": "LIKE",
                "payload": {
                    "parent_id": "post_67890",
                    "parent_type": "post",
                    "timestamp": "2023-10-15T12:34:56Z",
                    "priority": "normal"
                }
            }
        }
