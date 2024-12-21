from typing import Optional
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
    #created_at: datetime
    status: EventStatus
    retry_count: int
    user_id: str
    event_name: str
    payload: dict
