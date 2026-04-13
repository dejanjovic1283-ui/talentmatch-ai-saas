from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import Base, SessionLocal, engine
from models import Analysis
from schemas import AnalysisCreate, AnalysisResponse, AuthRequest, AuthResponse
from services import (
    analyze_resume_with_ai,
    build_analysis_payload,
    extract_text_from_pdf_bytes,
    login_user,
    signup_user,
    upload_file_to_gcs,
    verify_id_token,
)


app = FastAPI(title="TalentMatch AI SaaS Backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format.")

    id_token = authorization.replace("Bearer ", "").strip()
    if not id_token:
        raise HTTPException(status_code=401, detail="Missing Firebase ID token.")

    try:
        decoded = verify_id_token(id_token)
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/signup", response_model=AuthResponse)
def auth_signup(payload: AuthRequest):
    try:
        data = signup_user(payload.email, payload.password)
        return AuthResponse(
            email=data.get("email", payload.email),
            localId=data.get("localId", ""),
            idToken=data.get("idToken", ""),
            refreshToken=data.get("refreshToken", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/auth/login", response_model=AuthResponse)
def auth_login(payload: AuthRequest):
    try:
        data = login_user(payload.email, payload.password)
        return AuthResponse(
            email=data.get("email", payload.email),
            localId=data.get("localId", ""),
            idToken=data.get("idToken", ""),
            refreshToken=data.get("refreshToken", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        file_bytes = await file.read()
        resume_text = extract_text_from_pdf_bytes(file_bytes)

        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF.")

        safe_email = current_user.get("email", "unknown").replace("@", "_at_").replace(".", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        destination_name = f"resumes/{safe_email}/{timestamp}_{file.filename}"

        try:
            file_url = upload_file_to_gcs(file_bytes, destination_name)
        except Exception:
            file_url = None

        ai_result = analyze_resume_with_ai(resume_text, job_description)

        payload = build_analysis_payload(
            user_email=current_user.get("email", "unknown"),
            filename=file.filename,
            resume_text=resume_text,
            job_description=job_description,
            ai_result=ai_result,
            file_url=file_url,
        )

        analysis = Analysis(
            user_email=payload["user_email"],
            filename=payload["filename"],
            file_url=payload["file_url"],
            resume_text=payload["resume_text"],
            job_description=payload["job_description"],
            match_score=payload["match_score"],
            summary=payload["summary"],
            strengths="\n".join(payload["strengths"]),
            weaknesses="\n".join(payload["weaknesses"]),
            missing_skills="\n".join(payload["missing_skills"]),
            suggestions="\n".join(payload["suggestions"]),
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        return AnalysisResponse(
            id=analysis.id,
            user_email=analysis.user_email,
            filename=analysis.filename,
            file_url=analysis.file_url,
            match_score=analysis.match_score,
            summary=analysis.summary,
            strengths=payload["strengths"],
            weaknesses=payload["weaknesses"],
            missing_skills=payload["missing_skills"],
            suggestions=payload["suggestions"],
            created_at=analysis.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/history", response_model=list[AnalysisResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = (
        db.query(Analysis)
        .filter(Analysis.user_email == current_user.get("email", ""))
        .order_by(Analysis.created_at.desc())
        .all()
    )

    results = []
    for row in rows:
        results.append(
            AnalysisResponse(
                id=row.id,
                user_email=row.user_email,
                filename=row.filename,
                file_url=row.file_url,
                match_score=row.match_score,
                summary=row.summary,
                strengths=[x for x in (row.strengths or "").split("\n") if x.strip()],
                weaknesses=[x for x in (row.weaknesses or "").split("\n") if x.strip()],
                missing_skills=[x for x in (row.missing_skills or "").split("\n") if x.strip()],
                suggestions=[x for x in (row.suggestions or "").split("\n") if x.strip()],
                created_at=row.created_at,
            )
        )
    return results


@app.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_email == current_user.get("email", ""))
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return AnalysisResponse(
        id=row.id,
        user_email=row.user_email,
        filename=row.filename,
        file_url=row.file_url,
        match_score=row.match_score,
        summary=row.summary,
        strengths=[x for x in (row.strengths or "").split("\n") if x.strip()],
        weaknesses=[x for x in (row.weaknesses or "").split("\n") if x.strip()],
        missing_skills=[x for x in (row.missing_skills or "").split("\n") if x.strip()],
        suggestions=[x for x in (row.suggestions or "").split("\n") if x.strip()],
        created_at=row.created_at,
    )