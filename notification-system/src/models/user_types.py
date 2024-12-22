from enum import Enum

class UserType(str, Enum):
    ADMIN = "admin"
    PREMIUM = "premium"
    BASIC = "basic"
    FREE = "free"

