
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    email: EmailStr
    localId: str
    idToken: str
    refreshToken: str


class AnalysisCreate(BaseModel):
    filename: str
    job_description: str


class AnalysisResponse(BaseModel):
    id: int
    user_email: str
    filename: str
    file_url: Optional[str] = None
    match_score: int
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    missing_skills: list[str]
    suggestions: list[str]
    created_at: datetime

    class Config:
        from_attributes = True