# 🚀 TalentMatch AI SaaS

AI-powered platform that analyzes CVs against job descriptions and provides actionable feedback — helping candidates improve their chances of getting hired.

---

## 💡 Why this project exists

The job application process is inefficient and frustrating.

Candidates:
- Send dozens or hundreds of CVs
- Receive little to no feedback
- Don’t know how to improve their resumes

Recruiters:
- Spend hours manually reviewing CVs
- Struggle to quickly identify the best candidates

👉 TalentMatch AI automates this process using AI, providing **instant, structured, and actionable CV analysis**.

---

## ⚡ Core Features

- 🔑 User authentication (Firebase)
- 📄 Upload CV (PDF)
- 🧾 Paste job description
- 🤖 AI-powered analysis
- 📊 Match score calculation
- 🧠 Summary generation
- ✅ Strengths identification
- ❌ Weakness detection
- 💡 Actionable improvement suggestions
- 🕘 Analysis history tracking

---

## 🧠 Example Output

- Match Score: **80%**
- Summary: Candidate fits role but needs stronger Python emphasis
- Suggestions:
- Highlight Python experience
- Add Docker-based projects

---

## 🏗️ Tech Stack

Frontend:
- Streamlit

Backend:
- FastAPI

AI:
- OpenAI API

Authentication:
- Firebase Authentication

Storage:
- Firebase Storage

Database:
- SQLite (can be upgraded to PostgreSQL)

---

## 📁 Project Structure


talentmatch-ai-saas/
├── backend/
│ ├── .env
│ ├── app.db
│ ├── db.py
│ ├── main.py
│ ├── models.py
│ ├── requirements.txt
│ ├── schemas.py
│ ├── serviceAccountKey.json
│ └── services.py
├── frontend/
│ ├── .env
│ ├── app.py
│ └── requirements.txt
├── .dockerignore
├── .env
├── .gitignore
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── README.md

 ---

## ⚙️ Environment Setup

Backend (backend/.env)

- OPENAI_API_KEY=your_openai_key
- FIREBASE_API_KEY=your_firebase_api_key
- GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
- DATABASE_URL=sqlite:///./app.db

Root (.env)

- FIREBASE_API_KEY=your_firebase_api_key

 ---

## ▶️ Run Locally (without Docker)

Backend:

- cd backend
- uvicorn main:app --reload

Frontend:

- cd frontend
- streamlit run app.py

 ---

## 🌍 Vision

- This is just the MVP.

Future plans:

- Resume optimization suggestions (auto-rewrite)
- ATS score simulation
- Job matching engine
- Recruiter dashboard

 ---

## 👤 Author

**Dejan Jović**
**dejan.jovic1283@gmail.com**

 ---

## ⭐ Why this matters

This project demonstrates:

- Full-stack development (FastAPI + Streamlit)
- API integration (OpenAI, Firebase)
- Authentication & security
- Real-world SaaS architecture
- Docker & deployment readiness

 ---

## 👉 This is not just a project — it’s a product. 

 ---