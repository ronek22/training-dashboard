from pydantic import BaseModel


class CoachNote(BaseModel):
    date: str
    category: str
    content: str
