import os
import certifi
import ssl

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = ssl._create_unverified_context

import json
import re
from io import BytesIO
from typing import Any, Dict, Optional

import firebase_admin
import requests
from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth, credentials
from google.cloud import storage
from openai import OpenAI
from PyPDF2 import PdfReader

load_dotenv()




OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
BUCKET_NAME = os.getenv("BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


def get_openai_client() -> OpenAI:
    api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def init_firebase():
    import os
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not cred_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")

    if not os.path.exists(cred_path):
        raise ValueError(f"Service account file not found: {cred_path}")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)


def signup_user(email: str, password: str) -> Dict[str, Any]:
    """
    Creates a user via Firebase Authentication REST API.
    """
    if not FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }

    response = requests.post(url, json=payload, timeout=30)
    data = response.json()

    if response.status_code != 200:
        message = data.get("error", {}).get("message", "Firebase signup failed.")
        raise ValueError(message)

    return data


def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    Logs in a user via Firebase Authentication REST API.
    """
    if not FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }

    response = requests.post(url, json=payload, timeout=30)
    data = response.json()

    if response.status_code != 200:
        message = data.get("error", {}).get("message", "Firebase login failed.")
        raise ValueError(message)

    return data


def verify_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifies Firebase ID token with Firebase Admin SDK.
    """
    init_firebase()
    decoded = firebase_auth.verify_id_token(id_token)
    return decoded


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """
    Extracts text from an uploaded PDF file.
    """
    try:
        reader = PdfReader(BytesIO(file_bytes))
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}") from e


def upload_file_to_gcs(file_bytes: bytes, destination_blob_name: str, content_type: str = "application/pdf") -> str:
    """
    Uploads file to Google Cloud Storage and returns gs:// path.
    """
    if not BUCKET_NAME:
        raise ValueError("BUCKET_NAME is not set.")

    client = storage.Client(project=GOOGLE_CLOUD_PROJECT or None)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file_bytes, content_type=content_type)

    return f"gs://{BUCKET_NAME}/{destination_blob_name}"


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9+#./ -]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def calculate_keyword_match_score(resume_text: str, job_description: str) -> int:
    """
    Simple deterministic keyword overlap score from 0 to 100.
    Useful as a quick score before/alongside LLM analysis.
    """
    if not resume_text.strip() or not job_description.strip():
        return 0

    jd_words = set(normalize_text(job_description).split())
    resume_words = set(normalize_text(resume_text).split())

    filtered_jd_words = {w for w in jd_words if len(w) > 2}
    if not filtered_jd_words:
        return 0

    overlap = filtered_jd_words.intersection(resume_words)
    score = int((len(overlap) / len(filtered_jd_words)) * 100)
    return max(0, min(score, 100))


def analyze_resume_with_ai(resume_text: str, job_description: str) -> Dict[str, Any]:
    """
    Main AI analysis for CV vs job description.
    Returns structured JSON.
    """
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")

    if not job_description.strip():
        raise ValueError("Job description is empty.")

    client = get_openai_client()
    quick_score = calculate_keyword_match_score(resume_text, job_description)

    prompt = f"""
You are an expert technical recruiter and CV reviewer.

Analyze the candidate resume against the job description.

Return ONLY valid JSON with this exact structure:
{{
  "match_score": 0,
  "summary": "",
  "strengths": ["", "", ""],
  "weaknesses": ["", "", ""],
  "missing_skills": ["", "", ""],
  "suggestions": ["", "", ""]
}}

Rules:
- match_score must be an integer from 0 to 100
- summary must be short and practical
- strengths, weaknesses, missing_skills, suggestions must each contain 3 to 6 items
- be concrete, concise, and job-oriented
- do not include markdown
- do not include any text outside JSON

Quick keyword overlap score: {quick_score}/100

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}
""".strip()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a precise resume-job matching assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    data["match_score"] = int(data.get("match_score", quick_score))
    data["match_score"] = max(0, min(data["match_score"], 100))

    if "summary" not in data or not isinstance(data["summary"], str):
        data["summary"] = "Resume analysis completed."

    for key in ["strengths", "weaknesses", "missing_skills", "suggestions"]:
        if key not in data or not isinstance(data[key], list):
            data[key] = []

    return data


def build_analysis_payload(
    user_email: str,
    filename: str,
    resume_text: str,
    job_description: str,
    ai_result: Dict[str, Any],
    file_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Helper to build a clean analysis object for DB saving or API response.
    """
    return {
        "user_email": user_email,
        "filename": filename,
        "file_url": file_url,
        "resume_text": resume_text,
        "job_description": job_description,
        "match_score": ai_result.get("match_score", 0),
        "summary": ai_result.get("summary", ""),
        "strengths": ai_result.get("strengths", []),
        "weaknesses": ai_result.get("weaknesses", []),
        "missing_skills": ai_result.get("missing_skills", []),
        "suggestions": ai_result.get("suggestions", []),
    }