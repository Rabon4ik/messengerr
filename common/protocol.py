import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Message:
    type: str                    # login, register, message, error, user_list, history
    from_user: Optional[str] = None
    to_user: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    users: Optional[List[str]] = None
    history: Optional[List[dict]] = None
    success: bool = True

    def to_json(self) -> str:
        data = {k: v for k, v in self.__dict__.items() if v is not None}
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def from_json(data: str) -> 'Message':
        return Message(**json.loads(data))