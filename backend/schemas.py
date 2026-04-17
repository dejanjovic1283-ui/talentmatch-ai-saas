from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr


class AnalyzeResponse(BaseModel):
    id: int
    user_email: EmailStr
    filename: str
    match_score: int
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    missing_skills: List[str]
    suggestions: List[str]
    created_at: datetime


class HistoryItemResponse(BaseModel):
    id: int
    user_email: EmailStr
    filename: str
    match_score: int
    summary: str
    created_at: datetime


class HistoryDetailResponse(BaseModel):
    id: int
    user_email: EmailStr
    filename: str
    match_score: int
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    missing_skills: List[str]
    suggestions: List[str]
    created_at: datetime