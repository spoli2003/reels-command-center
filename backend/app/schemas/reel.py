from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    hook: Optional[str] = None


class ReelRead(BaseModel):
    id: int
    title: str
    category: str
    hook: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
