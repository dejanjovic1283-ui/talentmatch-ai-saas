import os
import re
from io import BytesIO
from typing import List, Optional

import numpy as np
import pandas as pd
import pdfplumber
import streamlit as st
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧠",
    layout="wide",
)


# =========================
# CUSTOM CSS
# =========================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f8fafc;
    }

    .hero-card {
        background: linear-gradient(135deg, #0f172a, #1e293b, #111827);
        padding: 28px;
        border-radius: 22px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.22);
    }

    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .hero-subtitle {
        font-size: 1rem;
        opacity: 0.92;
    }

    .section-card {
        background: white;
        padding: 20px;
        border-radius: 18px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(15, 23, 42, 0.05);
        margin-bottom: 18px;
    }

    .score-box {
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(135deg, #eff6ff, #f8fafc);
        border: 1px solid #dbeafe;
        margin: 14px 0 20px 0;
    }

    .metric-chip {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        background: #eef2ff;
        border: 1px solid #c7d2fe;
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 0.92rem;
        font-weight: 600;
        color: #3730a3;
    }

    .mini-note {
        color: #64748b;
        font-size: 0.93rem;
        margin-top: 6px;
    }

    .subtle-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 8px;
        color: #0f172a;
    }

    .login-card {
        max-width: 420px;
        margin: 60px auto;
        background: white;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10);
        border: 1px solid rgba(15, 23, 42, 0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# LOGIN
# =========================
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "1234")


def login_screen():
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("## 🔐 Login")
    st.caption("Demo login for SaaS-style experience")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# OPENAI CONFIG
# =========================
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4.1-mini"


def load_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    if not api_key.startswith("sk-"):
        raise ValueError("OPENAI_API_KEY does not look valid.")
    return OpenAI(api_key=api_key)


# =========================
# HELPERS
# =========================
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_text(uploaded_file) -> str:
    pages_text = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)
    return clean_text("\n".join(pages_text))


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    text = clean_text(text)
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def embed_texts(texts: List[str]) -> np.ndarray:
    client = load_openai_client()

    clean_texts = [clean_text(t) for t in texts if clean_text(t)]
    if not clean_texts:
        return np.array([], dtype=np.float32)

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=clean_texts,
    )

    vectors = [item.embedding for item in response.data]
    return np.array(vectors, dtype=np.float32)


@st.cache_data(show_spinner="Creating semantic index...")
def build_vector_store(chunks: List[str]):
    if not chunks:
        return None

    vectors = embed_texts(chunks)
    if vectors.size == 0:
        return None

    vectors = normalize_vectors(vectors)

    return {
        "chunks": chunks,
        "vectors": vectors,
    }


def retrieve_relevant_chunks(query: str, store, top_k: int = 5) -> List[str]:
    if not query or not store:
        return []

    query_vec = embed_texts([query])
    if query_vec.size == 0:
        return []

    query_vec = normalize_vectors(query_vec)[0]
    scores = store["vectors"] @ query_vec
    best_idx = np.argsort(scores)[::-1][:top_k]

    return [store["chunks"][i] for i in best_idx]


def build_context(resume_text: str, job_description: str, retrieved_chunks: List[str]) -> str:
    context_parts = []

    if resume_text:
        context_parts.append("RESUME:\n" + resume_text[:12000])

    if job_description and clean_text(job_description):
        context_parts.append("JOB DESCRIPTION:\n" + clean_text(job_description)[:6000])

    if retrieved_chunks:
        context_parts.append("RELEVANT CHUNKS:\n" + "\n\n".join(retrieved_chunks))

    return "\n\n".join(context_parts)


def estimate_match_score(resume_text: str, job_description: str) -> Optional[int]:
    if not resume_text or not clean_text(job_description):
        return None

    resume_words = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-\+#\.]{1,}\b", resume_text.lower()))
    jd_words = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-\+#\.]{1,}\b", job_description.lower()))

    jd_words = {w for w in jd_words if len(w) > 2}
    if not jd_words:
        return None

    overlap = len(resume_words & jd_words)
    score = int((overlap / len(jd_words)) * 100)

    return max(15, min(score, 95))


def estimate_subscores(resume_text: str, job_description: str):
    if not resume_text:
        return None

    r = resume_text.lower()
    j = job_description.lower() if job_description else ""

    technical_keywords = ["python", "api", "rest", "git", "docker", "streamlit", "sql"]
    ml_keywords = ["machine learning", "ml", "nlp", "embedding", "llm", "openai", "ai"]
    deployment_keywords = ["docker", "cloud", "deploy", "google cloud", "run", "container"]

    def score_keywords(keywords):
        if not j:
            return None

        jd_hits = sum(1 for k in keywords if k in j)
        if jd_hits == 0:
            jd_hits = len(keywords)

        resume_hits = sum(1 for k in keywords if k in r)
        score = int((resume_hits / jd_hits) * 100) if jd_hits else 0
        return max(20, min(score, 100))

    technical = score_keywords(technical_keywords)
    ml = score_keywords(ml_keywords)
    deploy = score_keywords(deployment_keywords)

    return {
        "Technical Skills": technical if technical is not None else 60,
        "ML / NLP": ml if ml is not None else 50,
        "Tools / Deployment": deploy if deploy is not None else 55,
    }


def ask_llm(context: str, question: str, chat_history: List[dict]) -> str:
    client = load_openai_client()

    system_prompt = """
You are an expert career coach and resume assistant.

Your job is to:
- analyze the user's resume
- compare it with the job description
- identify strengths, weaknesses, and missing skills
- give specific, practical, honest advice
- keep answers clear, structured, and actionable

Rules:
- Be concise but useful.
- Use bullet points when helpful.
- If the user asks about fit, include:
  1. overall fit
  2. strengths
  3. missing skills
  4. resume improvements
  5. next steps
- If the user asks for projects, suggest practical portfolio projects.
- Never invent resume facts that are not present in the provided context.
""".strip()

    messages = []

    messages.append({
        "role": "system",
        "content": system_prompt
    })

    for item in chat_history[-6:]:
        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}"
    })

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.3,
    )

    return response.choices[0].message.content or "No response generated."


def generate_pdf_report(
    overall_score: Optional[int],
    subscores: Optional[dict],
    question: str,
    answer: str,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    question = question or "No question provided."
    answer = answer or "No analysis available."

    story.append(Paragraph("AI Career Copilot Report", styles["Title"]))
    story.append(Spacer(1, 16))

    if overall_score is not None:
        story.append(Paragraph(f"<b>Overall Match Score:</b> {overall_score}/100", styles["Normal"]))
        story.append(Spacer(1, 8))

    if subscores:
        story.append(Paragraph("<b>Category Scores:</b>", styles["Heading2"]))
        for key, value in subscores.items():
            story.append(Paragraph(f"- {key}: {value}%", styles["Normal"]))
        story.append(Spacer(1, 12))

    story.append(Paragraph("<b>User Question:</b>", styles["Heading2"]))
    story.append(Paragraph(question, styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>AI Analysis:</b>", styles["Heading2"]))
    for paragraph in answer.split("\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph, styles["Normal"]))
            story.append(Spacer(1, 6))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# =========================
# SESSION STATE
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "messages" not in st.session_state:
    st.session_state.messages = []

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "job_description" not in st.session_state:
    st.session_state.job_description = ""

if "last_question" not in st.session_state:
    st.session_state.last_question = ""

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

if "overall_score" not in st.session_state:
    st.session_state.overall_score = None

if "subscores" not in st.session_state:
    st.session_state.subscores = None


# =========================
# LOGIN GATE
# =========================
if not st.session_state.logged_in:
    login_screen()
    st.stop()


# =========================
# HEADER + LOGOUT
# =========================
header_col1, header_col2 = st.columns([6, 1])

with header_col1:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">🧠 AI Career Copilot</div>
            <div class="hero-subtitle">
                Upload your resume, add a job description, and get AI-powered career analysis,
                scoring, project recommendations, and a downloadable PDF report.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_col2:
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.messages = []
        st.rerun()


# =========================
# MAIN LAYOUT
# =========================
left, right = st.columns([1, 1])

with left:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="subtle-title">📄 Upload Resume</div>', unsafe_allow_html=True)
    st.caption("Upload your resume as a PDF file.")

    uploaded_file = st.file_uploader(
        "Upload Resume",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        with st.spinner("Reading and indexing your resume..."):
            resume_text = extract_pdf_text(uploaded_file)
            st.session_state.resume_text = resume_text

            chunks = chunk_text(resume_text)
            st.session_state.vector_store = build_vector_store(chunks)

        st.success("Resume uploaded and indexed successfully.")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="subtle-title">🧾 Job Description</div>', unsafe_allow_html=True)

    job_description = st.text_area(
        "Job Description",
        value=st.session_state.job_description,
        placeholder="Paste the job description here...",
        height=250,
        label_visibility="collapsed",
    )
    st.session_state.job_description = job_description

    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# SCORE SECTION
# =========================
if st.session_state.resume_text:
    overall_score = estimate_match_score(
        st.session_state.resume_text,
        st.session_state.job_description,
    )

    subscores = estimate_subscores(
        st.session_state.resume_text,
        st.session_state.job_description,
    )

    st.session_state.overall_score = overall_score
    st.session_state.subscores = subscores

    if overall_score is not None:
        st.markdown(
            f"""
            <div class="score-box">
                <div style="font-size:1.2rem; font-weight:800; color:#0f172a;">
                    Quick Match Score: {overall_score}/100
                </div>
                <div class="mini-note">
                    Fast screening estimate based on alignment between your resume and the job description.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(overall_score / 100)

    if subscores:
        chip_html = "".join(
            [f'<span class="metric-chip">{k}: {v}%</span>' for k, v in subscores.items()]
        )
        st.markdown(chip_html, unsafe_allow_html=True)

        df = pd.DataFrame(
            {
                "Category": list(subscores.keys()),
                "Score": list(subscores.values()),
            }
        )
        st.bar_chart(df.set_index("Category"))


# =====================
# QUICK ACTIONS
# =====================

col1, col2 = st.columns([4,1])

with col1:
    st.markdown("### Your Career Chat")

with col2:
    if st.button("Reset"):
        st.session_state.clear()
        st.rerun()

suggestion_cols = st.columns(4)

default_questions = [
    "How well does my resume match this job?",
    "What skills am I missing for this role?",
    "How can I improve my CV for this position?",
    "Suggest 3 projects to improve my chances.",
]

for i, q in enumerate(default_questions):
    with suggestion_cols[i]:
        if st.button(q, use_container_width=True):
            st.session_state["pending_question"] = q


# =========================
# CHAT HISTORY
# =========================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =========================
# CHAT INPUT
# =========================
user_question = st.chat_input("Ask something about your resume, job fit, or improvements...")

if not user_question and "pending_question" in st.session_state:
    user_question = st.session_state["pending_question"]
    del st.session_state["pending_question"]

if user_question:
    if not st.session_state.resume_text:
        st.warning("Please upload your resume first.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_question})
        st.session_state.last_question = user_question or ""

        retrieval_query = user_question
        if clean_text(st.session_state.job_description):
            retrieval_query += "\n\n" + clean_text(st.session_state.job_description)

        retrieved_chunks = retrieve_relevant_chunks(
            query=retrieval_query,
            store=st.session_state.vector_store,
            top_k=5,
        )

        context = build_context(
            resume_text=st.session_state.resume_text,
            job_description=st.session_state.job_description,
            retrieved_chunks=retrieved_chunks,
        )

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                answer = ask_llm(
                    context=context,
                    question=user_question,
                    chat_history=st.session_state.messages,
                )
                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.last_answer = answer or ""


# =========================
# PDF EXPORT
# =========================
if st.session_state.last_answer:
    st.markdown("## 📄 Export Report")

    pdf_bytes = generate_pdf_report(
        overall_score=st.session_state.overall_score,
        subscores=st.session_state.subscores,
        question=st.session_state.last_question or "",
        answer=st.session_state.last_answer or "",
    )

    st.download_button(
        label="Download PDF Report",
        data=pdf_bytes,
        file_name="AI_Career_Copilot_Report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )