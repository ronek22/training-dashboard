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
