# 🚀 TalentMatch AI SaaS

AI-powered SaaS application for resume analysis and job matching.

## 🌐 Overview

TalentMatch AI allows users to:

- Create an account and log in
- Upload a CV (PDF)
- Paste a job description
- Get an AI-powered match score
- Receive structured feedback:
- strengths
- weaknesses
- missing skills
- improvement suggestions
- View analysis history

## ✨ Features

- Authentication (Firebase / Identity Platform)
- Resume upload (PDF)
- AI analysis (OpenAI)
- Match scoring system
- History per user
- Dockerized backend and frontend
- Cloud-ready architecture

## 🛠 Tech Stack

- Python 3.13
- FastAPI (backend)
- Streamlit (frontend)
- OpenAI API
- Firebase Authentication
- SQLAlchemy
- Docker
- Google Cloud Run
- Google Cloud Storage

## 📁 Project Structure

talentmatch-ai-saas/
│
├── backend/
│ ├── main.py
│ ├── db.py
│ ├── models.py
│ ├── schemas.py
│ ├── services.py
│ ├── requirements.txt
│ └── .env
│
├── frontend/
│ ├── app.py
│ └── requirements.txt
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── .dockerignore
├── .gitignore
└── README.md

## 🔐 Environment Variables

Create:

- backend/.env

Example:

- OPENAI_API_KEY=your_openai_api_key
- FIREBASE_API_KEY=your_firebase_api_key
- GOOGLE_APPLICATION_CREDENTIALS=path_to_service_account.json
- GOOGLE_CLOUD_PROJECT=your_project_id
- BUCKET_NAME=your_bucket_name
- DATABASE_URL=sqlite:///./app.db

## ▶️ Run Locally

Backend

- cd backend
- pip install -r requirements.txt
- python -m uvicorn main:app --reload

Backend runs on:

- http://127.0.0.1:8000

Frontend

- cd frontend
- pip install -r requirements.txt
- streamlit run app.py

Frontend runs on:

- http://localhost:8501

## 🐳 Docker

Backend

- docker build -f Dockerfile.backend -t talentmatch-backend .

Frontend

- docker build -f Dockerfile.frontend -t talentmatch-frontend .

## ☁️ Deployment

Deploy using Google Cloud Run:

- Backend → Cloud Run service
- Frontend → Cloud Run service
- Secrets → Secret Manager
- Storage → Cloud Storage
- Auth → Firebase / Identity Platform

## 👤 Author

**Dejan Jović**
**dejan.jovic1283@gmail.com**