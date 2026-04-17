import json
import os
import re
import ssl
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import certifi
import firebase_admin
import requests
from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth, credentials
from openai import OpenAI
from PyPDF2 import PdfReader

load_dotenv()

CERT_PATH = certifi.where()
os.environ["SSL_CERT_FILE"] = CERT_PATH
os.environ["REQUESTS_CA_BUNDLE"] = CERT_PATH
os.environ["CURL_CA_BUNDLE"] = CERT_PATH

# Enable this only for local development if Windows SSL continues to fail.
DISABLE_SSL_VERIFY = os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"

if DISABLE_SSL_VERIFY:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ssl._create_default_https_context = ssl._create_unverified_context

    original_request = requests.Session.request

    def patched_request(self, method, url, **kwargs):
        kwargs.setdefault("verify", False)
        return original_request(self, method, url, **kwargs)

    requests.Session.request = patched_request


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./serviceAccountKey.json")


def resolve_credentials_path() -> str:
    """Resolve the service account path relative to the current file."""
    raw_path = GOOGLE_APPLICATION_CREDENTIALS or "./serviceAccountKey.json"
    path = Path(raw_path)

    if not path.is_absolute():
        path = Path(__file__).resolve().parent / raw_path

    return str(path.resolve())


def get_openai_client() -> OpenAI:
    """Create an OpenAI client using the API key from environment variables."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in the .env file.")

    return OpenAI(api_key=OPENAI_API_KEY)


def init_firebase() -> None:
    """Initialize Firebase Admin SDK once."""
    if firebase_admin._apps:
        return

    cred_path = resolve_credentials_path()
    if not os.path.exists(cred_path):
        raise ValueError(f"Service account file not found: {cred_path}")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)


def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """Verify a Firebase ID token using Firebase Admin SDK."""
    if not id_token:
        raise ValueError("ID token is missing.")

    init_firebase()
    return firebase_auth.verify_id_token(id_token, check_revoked=False)


def verify_token_with_rest_api(id_token: str) -> Dict[str, Any]:
    """Fallback verification through Firebase Identity Toolkit REST API."""
    if not FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set in the .env file.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    response = requests.post(
        url,
        json={"idToken": id_token},
        timeout=30,
        verify=False if DISABLE_SSL_VERIFY else CERT_PATH,
    )
    response.raise_for_status()

    payload = response.json()
    users = payload.get("users", [])
    if not users:
        raise ValueError("User not found for the provided token.")

    user = users[0]
    return {
        "uid": user.get("localId"),
        "email": user.get("email"),
        "email_verified": user.get("emailVerified", False),
        "name": user.get("displayName"),
    }


def clean_text(text: str) -> str:
    """Normalize extracted text for analysis."""
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def normalize_list(value: Any) -> List[str]:
    """Convert a value to a list of clean strings."""
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        parts = re.split(r"[\n•\-]+", value)
        return [part.strip() for part in parts if part.strip()]

    return [str(value).strip()]


def normalize_score(value: Any) -> int:
    """Convert a score to an integer in the range 0-100."""
    try:
        score = int(value)
        return max(0, min(100, score))
    except Exception:
        return 0


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    if not file_bytes:
        raise ValueError("The uploaded PDF file is empty.")

    try:
        reader = PdfReader(BytesIO(file_bytes))
        pages: List[str] = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text)

        text = clean_text("\n\n".join(pages))
        if not text:
            raise ValueError("Could not extract text from the PDF.")

        return text
    except Exception as exc:
        raise ValueError(f"PDF processing failed: {exc}") from exc


def build_analysis_messages(cv_text: str, job_description: str) -> List[Dict[str, str]]:
    """Build the messages sent to the OpenAI model."""
    cv_text = cv_text[:12000]
    job_description = job_description[:4000]

    system_prompt = (
        "You are an expert technical recruiter. "
        "Compare the candidate CV against the job description and return strict JSON only."
    )

    user_prompt = f"""
Analyze this CV against the job description.

Return JSON with exactly these keys:
{{
  "match_score": 0-100,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "missing_skills": ["..."],
  "suggestions": ["..."],
  "summary": "short paragraph"
}}

Rules:
- match_score must be an integer from 0 to 100
- strengths, weaknesses, missing_skills, and suggestions must be arrays of short strings
- summary must be concise and useful
- return valid JSON only
- answer in English

JOB DESCRIPTION:
{job_description}

CV TEXT:
{cv_text}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_analysis_response(raw_text: str) -> Dict[str, Any]:
    """Parse the OpenAI response into structured analysis output."""
    raw_text = strip_code_fences(raw_text)

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise ValueError("The model response is not valid JSON.")
        data = json.loads(match.group(0))

    return {
        "match_score": normalize_score(data.get("match_score")),
        "strengths": normalize_list(data.get("strengths")),
        "weaknesses": normalize_list(data.get("weaknesses")),
        "missing_skills": normalize_list(data.get("missing_skills")),
        "suggestions": normalize_list(data.get("suggestions")),
        "summary": str(data.get("summary", "")).strip(),
    }


def analyze_cv_text(cv_text: str, job_description: str) -> Dict[str, Any]:
    """Run CV analysis against a job description using OpenAI."""
    if not cv_text.strip():
        raise ValueError("CV text is empty.")

    if not job_description.strip():
        raise ValueError("Job description is empty.")

    client = get_openai_client()
    messages = build_analysis_messages(cv_text=cv_text, job_description=job_description)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
    )

    raw_text = response.choices[0].message.content or ""
    return parse_analysis_response(raw_text)


def analyze_cv_file(file_bytes: bytes, job_description: str) -> Dict[str, Any]:
    """Extract text from a PDF and analyze it against the job description."""
    cv_text = extract_text_from_pdf(file_bytes)
    return analyze_cv_text(cv_text=cv_text, job_description=job_description)