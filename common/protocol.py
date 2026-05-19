import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Message:
    type: str
    from_user: Optional[str] = None
    to_user: Optional[str] = None        # для личных сообщений
    group_id: Optional[str] = None       # для групповых сообщений
    content: Optional[str] = None
    timestamp: Optional[str] = None
    users: Optional[List[str]] = None
    history: Optional[List[dict]] = None
    success: bool = True
    online: Optional[bool] = None
    # Групповые поля
    group_name: Optional[str] = None
    group_members: Optional[List[str]] = None
    groups: Optional[List[dict]] = None  # список групп [{id, name, members}]
    target_user: Optional[str] = None    # для кика / добавления

    def to_json(self) -> str:
        data = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
            if k == 'success' and v is True:
                continue  # не гоним лишний трафик, True — дефолт
            data[k] = v
        # success=False всегда сериализуем
        if not self.success:
            data['success'] = False
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def from_json(data: str) -> 'Message':
        raw = json.loads(data)
        known = {k: v for k, v in raw.items() if k in Message.__dataclass_fields__}
        return Message(**known)