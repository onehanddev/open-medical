from pydantic import BaseModel
from typing import Literal

class ChatHistory(BaseModel):
    role: Literal['user', 'assistant']
    content: str

class AskPostRequest(BaseModel):
    query: str
    history: list[ChatHistory] = []