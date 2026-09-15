from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---- auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    company: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    company: Optional[str] = None
    plan: str = "free"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---- conversions ----
class ConversionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)          # e.g. "mnist_cnn.onnx"
    target: str = Field(min_length=1, max_length=60)         # e.g. "cortex-m4f"
    quant: str = "int8"                                      # none | int16 | int8
    goal: str = "size"                                       # size | speed


class ConversionPublic(BaseModel):
    id: str
    name: str
    target: str
    quant: str
    goal: str
    status: str                                              # queued|building|done|failed
    flash: Optional[str] = None
    ram: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
