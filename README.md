# 🧠 AI Career Copilot

AI-powered resume analyzer and career assistant that evaluates your CV against job descriptions using semantic embeddings and LLM reasoning.

👉 Built with: Streamlit + OpenAI + Google Cloud Run

---

## 🚀 Live Demo

👉 https://career-ai-assistant-342313441373.europe-west1.run.app

---

## 📌 Features

- 📄 Upload CV (PDF parsing)
- 🔐 Demo login screen
- 🧠 AI career assistant (LLM-powered chat)
- 🔍 Semantic search (OpenAI embeddings)
- 📊 Smart match scoring system
- 📈 Visual score charts
- 💬 Interactive chat interface
- 📄 PDF report export
- ☁️ Cloud deployment (Google Cloud Run)

---

## 🛠 Tech Stack

- Python 3.13
- Streamlit
- OpenAI API
- NumPy
- Pandas
- PDFPlumber
- ReportLab
- Docker
- Google Cloud Run

---

## ⚙️ Installation (Local)

```bash
git clone https://github.com/dejanjovic1283-ui/career-ai-copilot.git
cd career-ai-copilot
pip install -r requirements.txt

---

## 🔑 Environment Variables

```bash
OPENAI_API_KEY=your_api_key_here
APP_USERNAME=admin
APP_PASSWORD=1234

---

## ▶️ Run Locally

```bash
- streamlit run app.py

---

## ☁️ Deployment (Google Cloud Run)

```bash
- gcloud builds submit --tag gcr.io/career-ai-assistant-342313441373/career-ai

```bash
- gcloud run deploy career-ai-assistant \
--image gcr.io/career-ai-assistant-342313441373/career-ai \
--platform managed \
--region europe-west1 \
--allow-unauthenticated

```bash
- gcloud run services update career-ai-assistant \
--set-env-vars OPENAI_API_KEY=your_api_key,APP_USERNAME=admin,APP_PASSWORD=1234