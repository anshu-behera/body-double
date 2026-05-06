from pydantic import BaseModel
from typing import List, Optional


class Event(BaseModel):
    app: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    timestamp: float
    meta_description: Optional[str] = None
    headings: Optional[List[str]] = None
    body_snippet: Optional[str] = None
