from typing import Optional

from pydantic import BaseModel


class CoachNote(BaseModel):
    date: str
    category: str
    content: str


class CoachChatMessageCreate(BaseModel):
    conversation_id: int
    role: str
    content: str


class CoachChatConversationCreate(BaseModel):
    title: str = "New conversation"


class CoachChatContextOpen(BaseModel):
    context_kind: str
    context_id: str
    title: str
    opener: Optional[str] = None
