import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


st.set_page_config(page_title="TalentMatch AI SaaS", page_icon="🚀", layout="wide")


BACKEND_URL = st.secrets.get(
    "API_BASE_URL",
    os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
)

FIREBASE_API_KEY = st.secrets.get(
    "FIREBASE_API_KEY",
    os.getenv("FIREBASE_API_KEY", "")
)    


def init_session_state() -> None:
    """Initialize Streamlit session state keys."""
    defaults = {
        "id_token": None,
        "user_email": None,
        "auth_error": None,
        "auth_success": None,
        "analysis_result": None,
        "history_items": [],
        "selected_history_id": None,
        "selected_history_detail": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def firebase_sign_up(email: str, password: str) -> Dict[str, Any]:
    """Create a new Firebase user with email and password."""
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
        error_message = data.get("error", {}).get("message", "Sign up failed.")
        raise ValueError(error_message)

    return data


def firebase_sign_in(email: str, password: str) -> Dict[str, Any]:
    """Sign in an existing Firebase user with email and password."""
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
        error_message = data.get("error", {}).get("message", "Login failed.")
        raise ValueError(error_message)

    return data


def get_auth_headers() -> Dict[str, str]:
    """Build authorization headers for backend requests."""
    id_token = st.session_state.get("id_token")
    if not id_token:
        raise ValueError("Missing authentication token.")

    return {
        "Authorization": f"Bearer {id_token}",
    }


def analyze_resume(file_obj, job_description: str) -> Dict[str, Any]:
    """Send the uploaded PDF and job description to the backend."""
    headers = get_auth_headers()
    files = {
        "file": (file_obj.name, file_obj.getvalue(), "application/pdf"),
    }
    data = {
        "job_description": job_description,
    }

    response = requests.post(
        f"{BACKEND_URL}/analyze-resume",
        headers=headers,
        files=files,
        data=data,
        timeout=180,
    )

    payload = response.json()

    if response.status_code != 200:
        detail = payload.get("detail", "Resume analysis failed.")
        raise ValueError(detail)

    return payload


def fetch_history() -> List[Dict[str, Any]]:
    """Fetch the authenticated user's analysis history."""
    headers = get_auth_headers()
    response = requests.get(f"{BACKEND_URL}/history", headers=headers, timeout=30)
    payload = response.json()

    if response.status_code != 200:
        detail = payload.get("detail", "Failed to fetch history.")
        raise ValueError(detail)

    return payload


def fetch_history_item(record_id: int) -> Dict[str, Any]:
    """Fetch one history item by ID."""
    headers = get_auth_headers()
    response = requests.get(f"{BACKEND_URL}/history/{record_id}", headers=headers, timeout=30)
    payload = response.json()

    if response.status_code != 200:
        detail = payload.get("detail", "Failed to fetch history item.")
        raise ValueError(detail)

    return payload


def render_auth_sidebar() -> None:
    """Render authentication controls in the sidebar."""
    st.sidebar.title("Authentication")

    if st.session_state.get("id_token"):
        st.sidebar.success("Authenticated")
        st.sidebar.write(f"User: {st.session_state.get('user_email')}")

        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state["id_token"] = None
            st.session_state["user_email"] = None
            st.session_state["analysis_result"] = None
            st.session_state["history_items"] = []
            st.session_state["selected_history_id"] = None
            st.session_state["selected_history_detail"] = None
            st.session_state["auth_error"] = None
            st.session_state["auth_success"] = None
            st.rerun()

        st.sidebar.divider()
        st.sidebar.caption(f"Backend URL: {BACKEND_URL}")
        return

    action = st.sidebar.radio("Choose action", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button(action, use_container_width=True):
        st.session_state["auth_error"] = None
        st.session_state["auth_success"] = None

        try:
            if not email.strip() or not password.strip():
                raise ValueError("Email and password are required.")

            if action == "Sign Up":
                result = firebase_sign_up(email=email.strip(), password=password)
                st.session_state["auth_success"] = "Account created successfully. You can now use the app."
            else:
                result = firebase_sign_in(email=email.strip(), password=password)
                st.session_state["auth_success"] = "Login successful."

            st.session_state["id_token"] = result.get("idToken")
            st.session_state["user_email"] = result.get("email", email.strip())
            st.rerun()

        except Exception as exc:
            st.session_state["auth_error"] = str(exc)

    if st.session_state.get("auth_success"):
        st.sidebar.success(st.session_state["auth_success"])

    if st.session_state.get("auth_error"):
        st.sidebar.error(st.session_state["auth_error"])

    st.sidebar.divider()
    st.sidebar.caption(f"Backend URL: {BACKEND_URL}")


def render_analysis_tab() -> None:
    """Render the main CV analysis UI."""
    st.subheader("Upload PDF CV")

    uploaded_file = st.file_uploader("Upload your CV", type=["pdf"])
    job_description = st.text_area(
        "Paste job description",
        height=180,
        placeholder="Paste the target job description here...",
    )

    if st.button("Analyze with AI", use_container_width=True):
        try:
            if not st.session_state.get("id_token"):
                raise ValueError("Please log in first.")

            if uploaded_file is None:
                raise ValueError("Please upload a PDF file.")

            if not job_description.strip():
                raise ValueError("Please enter a job description.")

            with st.spinner("Analyzing CV..."):
                result = analyze_resume(uploaded_file, job_description.strip())

            st.session_state["analysis_result"] = result
            st.success("Analysis completed successfully.")

        except Exception as exc:
            st.error(str(exc))

    result = st.session_state.get("analysis_result")
    if result:
        st.divider()
        st.subheader("Analysis Result")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Match Score", f"{result.get('match_score', 0)}%")
        with col2:
            st.write(f"**File:** {result.get('filename', 'N/A')}")

        st.write("**Summary**")
        st.info(result.get("summary", ""))

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Strengths**")
            for item in result.get("strengths", []):
                st.markdown(f"- {item}")

            st.write("**Missing Skills**")
            for item in result.get("missing_skills", []):
                st.markdown(f"- {item}")

        with col_b:
            st.write("**Weaknesses**")
            for item in result.get("weaknesses", []):
                st.markdown(f"- {item}")

            st.write("**Suggestions**")
            for item in result.get("suggestions", []):
                st.markdown(f"- {item}")


def render_history_tab() -> None:
    """Render the user's analysis history."""
    st.subheader("Analysis History")

    if not st.session_state.get("id_token"):
        st.info("Please log in to view your history.")
        return

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh History", use_container_width=True):
            try:
                st.session_state["history_items"] = fetch_history()
                st.session_state["selected_history_detail"] = None
            except Exception as exc:
                st.error(str(exc))

    if not st.session_state.get("history_items"):
        try:
            st.session_state["history_items"] = fetch_history()
        except Exception as exc:
            st.error(str(exc))
            return

    history_items = st.session_state.get("history_items", [])

    if not history_items:
        st.info("No history records found.")
        return

    options = {
        f"#{item['id']} | {item['filename']} | {item['match_score']}%": item["id"]
        for item in history_items
    }

    selected_label = st.selectbox("Select a history item", list(options.keys()))
    selected_id = options[selected_label]

    if st.button("Load Selected Item", use_container_width=True):
        try:
            st.session_state["selected_history_detail"] = fetch_history_item(selected_id)
        except Exception as exc:
            st.error(str(exc))

    detail = st.session_state.get("selected_history_detail")
    if detail:
        st.divider()
        st.write(f"**Record ID:** {detail.get('id')}")
        st.write(f"**Filename:** {detail.get('filename')}")
        st.write(f"**Created At:** {detail.get('created_at')}")
        st.metric("Match Score", f"{detail.get('match_score', 0)}%")

        st.write("**Summary**")
        st.info(detail.get("summary", ""))

        col_a, col_b = st.columns(2)

        with col_a:
            st.write("**Strengths**")
            for item in detail.get("strengths", []):
                st.markdown(f"- {item}")

            st.write("**Missing Skills**")
            for item in detail.get("missing_skills", []):
                st.markdown(f"- {item}")

        with col_b:
            st.write("**Weaknesses**")
            for item in detail.get("weaknesses", []):
                st.markdown(f"- {item}")

            st.write("**Suggestions**")
            for item in detail.get("suggestions", []):
                st.markdown(f"- {item}")


def main() -> None:
    """Render the full Streamlit application."""
    init_session_state()
    render_auth_sidebar()

    st.title("🚀 TalentMatch AI SaaS")
    st.caption("Upload your CV, compare it with a job description, and track analysis history.")

    if not st.session_state.get("id_token"):
        st.info("Please log in or create an account to start analyzing CVs.")
        return

    tab1, tab2 = st.tabs(["Analyze CV", "History"])

    with tab1:
        render_analysis_tab()

    with tab2:
        render_history_tab()


if __name__ == "__main__":
    main()