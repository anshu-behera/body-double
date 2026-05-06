# Shared schemas (expand later)

from pydantic import BaseModel
from typing import Optional

class Event(BaseModel):
    app: Optional[str]
    title: Optional[str]
    url: Optional[str]
    timestamp: float