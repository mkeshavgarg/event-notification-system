from enum import Enum

class EventType(str, Enum):
    LIKE = "LIKE"
    COMMENT = "COMMENT"
    SHARE = "SHARE"
    FOLLOW = "FOLLOW"
    UNFOLLOW = "UNFOLLOW"
    MENTION = "MENTION"
    MESSAGE = "MESSAGE"
    POST = "POST"
