import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


st.set_page_config(page_title="TalentMatch AI SaaS", page_icon="🚀", layout="wide")


def init_state() -> None:
    defaults = {
        "id_token": None,
        "refresh_token": None,
        "user_email": None,
        "local_id": None,
        "analysis_result": None,
        "history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def auth_headers() -> Dict[str, str]:
    token = st.session_state.get("id_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def signup(email: str, password: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/auth/signup",
        json={"email": email, "password": password},
        timeout=60,
    )
    data = response.json()
    if response.status_code != 200:
        raise ValueError(data.get("detail", "Signup failed."))
    return data


def login(email: str, password: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=60,
    )
    data = response.json()
    if response.status_code != 200:
        raise ValueError(data.get("detail", "Login failed."))
    return data


def analyze_cv(file, job_description: str) -> Dict[str, Any]:
    files = {
        "file": (file.name, file.getvalue(), "application/pdf")
    }
    data = {
        "job_description": job_description
    }

    response = requests.post(
        f"{API_BASE_URL}/analyze",
        headers=auth_headers(),
        files=files,
        data=data,
        timeout=300,
    )
    payload = response.json()
    if response.status_code != 200:
        raise ValueError(payload.get("detail", "Analysis failed."))
    return payload


def fetch_history() -> List[Dict[str, Any]]:
    response = requests.get(
        f"{API_BASE_URL}/history",
        headers=auth_headers(),
        timeout=60,
    )
    data = response.json()
    if response.status_code != 200:
        raise ValueError(data.get("detail", "Failed to load history."))
    return data


def logout() -> None:
    st.session_state["id_token"] = None
    st.session_state["refresh_token"] = None
    st.session_state["user_email"] = None
    st.session_state["local_id"] = None
    st.session_state["analysis_result"] = None
    st.session_state["history"] = []


def render_auth_sidebar() -> None:
    st.sidebar.header("Authentication")

    mode = st.sidebar.radio("Choose action", ["Login", "Sign Up"], key="auth_mode")
    email = st.sidebar.text_input("Email", key="auth_email")
    password = st.sidebar.text_input("Password", type="password", key="auth_password")

    if mode == "Sign Up":
        if st.sidebar.button("Create account", use_container_width=True):
            try:
                if not email or not password:
                    raise ValueError("Email and password are required.")
                result = signup(email, password)
                st.session_state["id_token"] = result["idToken"]
                st.session_state["refresh_token"] = result["refreshToken"]
                st.session_state["user_email"] = result["email"]
                st.session_state["local_id"] = result["localId"]
                st.sidebar.success("Account created and logged in.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))

    if mode == "Login":
        if st.sidebar.button("Login", use_container_width=True):
            try:
                if not email or not password:
                    raise ValueError("Email and password are required.")
                result = login(email, password)
                st.session_state["id_token"] = result["idToken"]
                st.session_state["refresh_token"] = result["refreshToken"]
                st.session_state["user_email"] = result["email"]
                st.session_state["local_id"] = result["localId"]
                st.sidebar.success("Logged in successfully.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Backend URL: {API_BASE_URL}")


def render_logged_in_sidebar() -> None:
    st.sidebar.success("Authenticated")
    st.sidebar.write(f"**User:** {st.session_state['user_email']}")
    if st.sidebar.button("Logout", use_container_width=True):
        logout()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Backend URL: {API_BASE_URL}")


def render_analysis_tab() -> None:
    st.subheader("Upload PDF CV")

    uploaded_file = st.file_uploader("Upload your CV", type=["pdf"])
    job_description = st.text_area("Paste job description", height=220)

    if st.button("Analyze with AI", use_container_width=True):
        try:
            if not st.session_state.get("id_token"):
                raise ValueError("Please log in first.")
            if uploaded_file is None:
                raise ValueError("Please upload a PDF CV.")
            if not job_description.strip():
                raise ValueError("Please paste a job description.")

            with st.spinner("Analyzing CV against the job description..."):
                result = analyze_cv(uploaded_file, job_description)
                st.session_state["analysis_result"] = result

            st.success("Analysis completed.")
        except Exception as e:
            st.error(str(e))

    result = st.session_state.get("analysis_result")
    if result:
        st.markdown("---")
        col1, col2 = st.columns([1, 2])

        with col1:
            st.metric("Match score", f"{result['match_score']}/100")
            st.write(f"**Filename:** {result['filename']}")
            if result.get("file_url"):
                st.write(f"**Stored file:** {result['file_url']}")

        with col2:
            st.write("### Summary")
            st.write(result["summary"])

        left, right = st.columns(2)

        with left:
            st.write("### Strengths")
            for item in result["strengths"]:
                st.write(f"- {item}")

            st.write("### Missing skills")
            for item in result["missing_skills"]:
                st.write(f"- {item}")

        with right:
            st.write("### Weaknesses")
            for item in result["weaknesses"]:
                st.write(f"- {item}")

            st.write("### Suggestions")
            for item in result["suggestions"]:
                st.write(f"- {item}")


def render_history_tab() -> None:
    st.subheader("Analysis History")

    if st.button("Refresh history"):
        try:
            st.session_state["history"] = fetch_history()
        except Exception as e:
            st.error(str(e))

    if not st.session_state.get("history"):
        try:
            st.session_state["history"] = fetch_history()
        except Exception:
            st.info("No history loaded yet.")

    history = st.session_state.get("history", [])
    if not history:
        st.info("No analyses yet.")
        return

    for item in history:
        with st.expander(f"{item['filename']} — {item['match_score']}/100 — {item['created_at']}"):
            st.write("### Summary")
            st.write(item["summary"])

            col1, col2 = st.columns(2)

            with col1:
                st.write("### Strengths")
                for x in item["strengths"]:
                    st.write(f"- {x}")

                st.write("### Missing skills")
                for x in item["missing_skills"]:
                    st.write(f"- {x}")

            with col2:
                st.write("### Weaknesses")
                for x in item["weaknesses"]:
                    st.write(f"- {x}")

                st.write("### Suggestions")
                for x in item["suggestions"]:
                    st.write(f"- {x}")


def main() -> None:
    init_state()

    st.title("🚀 TalentMatch AI SaaS")
    st.caption("Upload your CV, compare it with a job description, and track analysis history.")

    if st.session_state.get("id_token"):
        render_logged_in_sidebar()
        tab1, tab2 = st.tabs(["Analyze CV", "History"])
        with tab1:
            render_analysis_tab()
        with tab2:
            render_history_tab()
    else:
        render_auth_sidebar()
        st.info("Please log in or create an account to start analyzing CVs.")


if __name__ == "__main__":
    main()