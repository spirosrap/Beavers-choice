import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel

class ErrorType(Enum):
    VALIDATION = "validation_error"
    BUSINESS = "business_error"
    SYSTEM = "system_error"
    NETWORK = "network_error"

class AgentError(Exception):
    def __init__(self, error_type: ErrorType, message: str, retryable: bool = False):
        self.error_type = error_type
        self.message = message
        self.retryable = retryable
        super().__init__(message)

class Message(BaseModel):
    id: str = str(uuid.uuid4())
    to_agent: str
    from_agent: str
    content: Dict[str, Any]
    priority: int = 0
    created_at: datetime = datetime.now()
    expires_at: datetime = datetime.now() + timedelta(hours=24)
    acknowledged: bool = False
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessageQueue:
    def __init__(self):
        self._queue: List[Message] = []
    
    def send(self, message: Message) -> str:
        self._queue.append(message)
        self._queue.sort(key=lambda x: (-x.priority, x.created_at))
        return message.id
    
    def receive(self) -> Optional[Message]:
        if not self._queue:
            return None
        
        # Remove expired messages
        current_time = datetime.now()
        self._queue = [msg for msg in self._queue if msg.expires_at > current_time]
        
        return self._queue.pop(0) if self._queue else None
    
    def acknowledge(self, message_id: str) -> bool:
        for msg in self._queue:
            if msg.id == message_id:
                msg.acknowledged = True
                return True
        return False
    
    def get_queue_size(self) -> int:
        return len(self._queue)
    
    def clear_expired_messages(self) -> int:
        current_time = datetime.now()
        initial_size = len(self._queue)
        self._queue = [msg for msg in self._queue if msg.expires_at > current_time]
        return initial_size - len(self._queue) 