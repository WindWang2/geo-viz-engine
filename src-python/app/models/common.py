from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    backend: str


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
