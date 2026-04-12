from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
import json


class ConversationSession(SQLModel, table=True):
    __tablename__ = "conversation_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: str = Field(index=True, max_length=200)
    provider: str = Field(default="kustomer", max_length=50)
    agent_name: str = Field(default="default", max_length=100)
    openai_response_id: Optional[str] = Field(default=None, max_length=500)
    session_metadata: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_metadata(self) -> dict:
        try:
            return json.loads(self.session_metadata)
        except Exception:
            return {}

    def set_metadata(self, data: dict):
        self.session_metadata = json.dumps(data)
