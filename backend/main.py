from __future__ import annotations

from typing import Any, Generator, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from sqlalchemy.orm import Session # type: ignore

from db import Base, SessionLocal, engine
from models import AnalysisHistory
from schemas import AnalyzeResponse, HistoryDetailResponse, HistoryItemResponse
from services import analyze_cv_file, verify_firebase_token, verify_token_with_rest_api


Base.metadata.create_all(bind=engine)

app = FastAPI(title="TalentMatch AI SaaS API", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_list_field(value: Optional[str]) -> List[str]:
    """Convert a newline-separated database value to a clean list."""
    if not value:
        return []
    return [item.strip() for item in value.split("\n") if item.strip()]


def serialize_history_row(row: AnalysisHistory) -> HistoryDetailResponse:
    """Convert a database row into a detailed response model."""
    return HistoryDetailResponse(
        id=row.id, # type: ignore
        user_email=row.user_email, # type: ignore
        filename=row.filename, # type: ignore
        match_score=row.match_score, # type: ignore
        summary=row.summary or "", # type: ignore
        strengths=parse_list_field(row.strengths), # type: ignore
        weaknesses=parse_list_field(row.weaknesses), # type: ignore
        missing_skills=parse_list_field(row.missing_skills), # type: ignore
        suggestions=parse_list_field(row.suggestions), # type: ignore
        created_at=row.created_at, # type: ignore
    )


def extract_bearer_token(authorization: Optional[str]) -> str:
    """Extract the Firebase ID token from the Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header. Expected 'Bearer <token>'.",
        )

    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    return token


def authenticate_user(authorization: Optional[str]) -> dict[str, Any]:
    """Validate the Firebase token and return the decoded user payload."""
    token = extract_bearer_token(authorization)

    try:
        return verify_firebase_token(token)
    except Exception:
        try:
            return verify_token_with_rest_api(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


@app.get("/")
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"message": "Backend is running."}


@app.post("/analyze-resume", response_model=AnalyzeResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """
    Analyze an uploaded CV against a job description,
    save the result, and return structured analysis.
    """
    user = authenticate_user(authorization)

    user_email = user.get("email") or user.get("user_email") or user.get("emailAddress")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authenticated user email not found.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    try:
        analysis = analyze_cv_file(file_bytes=file_bytes, job_description=job_description)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    strengths = analysis.get("strengths", [])
    weaknesses = analysis.get("weaknesses", [])
    missing_skills = analysis.get("missing_skills", [])
    suggestions = analysis.get("suggestions", [])
    summary = str(analysis.get("summary", "")).strip()
    match_score = int(analysis.get("match_score", 0))

    row = AnalysisHistory(
        user_email=user_email,
        filename=file.filename,
        match_score=match_score,
        summary=summary,
        strengths="\n".join(strengths),
        weaknesses="\n".join(weaknesses),
        missing_skills="\n".join(missing_skills),
        suggestions="\n".join(suggestions),
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return AnalyzeResponse(
        id=row.id, # type: ignore
        user_email=row.user_email, # type: ignore
        filename=row.filename, # type: ignore
        match_score=row.match_score, # type: ignore
        summary=row.summary or "", # type: ignore
        strengths=strengths,
        weaknesses=weaknesses,
        missing_skills=missing_skills,
        suggestions=suggestions,
        created_at=row.created_at, # type: ignore
    )


@app.get("/history", response_model=List[HistoryItemResponse])
def get_history(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> List[HistoryItemResponse]:
    """Return analysis history for the authenticated user."""
    user = authenticate_user(authorization)

    user_email = user.get("email") or user.get("user_email") or user.get("emailAddress")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authenticated user email not found.")

    rows = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.user_email == user_email)
        .order_by(AnalysisHistory.created_at.desc())
        .all()
    )

    return [
        HistoryItemResponse(
            id=row.id, # type: ignore
            user_email=row.user_email, # type: ignore
            filename=row.filename, # type: ignore
            match_score=row.match_score, # type: ignore
            summary=row.summary or "", # type: ignore
            created_at=row.created_at, # type: ignore
        )
        for row in rows
    ]


@app.get("/history/{record_id}", response_model=HistoryDetailResponse)
def get_history_item(
    record_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> HistoryDetailResponse:
    """Return one history item for the authenticated user."""
    user = authenticate_user(authorization)

    user_email = user.get("email") or user.get("user_email") or user.get("emailAddress")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authenticated user email not found.")

    row = (
        db.query(AnalysisHistory)
        .filter(
            AnalysisHistory.id == record_id,
            AnalysisHistory.user_email == user_email,
        )
        .first()
    )

    if row is None:
        raise HTTPException(status_code=404, detail="History record not found.")

    return serialize_history_row(row)