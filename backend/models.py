from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text # type: ignore

from db import Base


class AnalysisHistory(Base):
    """
    Database model for storing CV analysis results.
    Each row represents one analyzed CV.
    """

    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    match_score = Column(Integer, nullable=False)
    summary = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    missing_skills = Column(Text, nullable=True)
    suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)