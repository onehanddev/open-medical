from pydantic import BaseModel

class AskPostRequest(BaseModel):
    query: str