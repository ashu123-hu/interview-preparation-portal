"""Interview Preparation Portal: Streamlit, SQLite, account login and AI feedback."""
from datetime import datetime
import html
import io
import json
import os
import random
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from database import (
    add_attempt, authenticate_user, create_question, delete_question,
    email_in_use, get_account_by_email, get_bookmarks, get_dashboard,
    get_interview_history, get_questions, init_db, register_user,
    save_interview_session, set_bookmark, update_question,
    update_user_password, username_exists,
)


def setting(name, default=""):
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.environ.get(name, default)


def ollama_chat(messages, num_predict=400, timeout=180):
    """Send a chat request to the configured local or self-hosted Ollama server."""
    ollama_url = setting("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    model_name = setting("OLLAMA_MODEL", "gemma3:1b").strip()
    request_body = json.dumps({
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": num_predict},
    }).encode("utf-8")
    request = Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result.get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty response. Try again or select another model.")
    return content


def transcribe_voice_answer(audio_bytes, language):
    """Transcribe a browser-recorded WAV answer with the free Google recognizer."""
    try:
        import speech_recognition as speech
    except ImportError as error:
        raise RuntimeError(
            "Voice transcription is not installed. Run `.venv\\Scripts\\python.exe -m pip install -r requirements.txt`, then restart the app."
        ) from error

    recognizer = speech.Recognizer()
    recognizer.operation_timeout = 25
    try:
        with speech.AudioFile(io.BytesIO(audio_bytes)) as source:
            recording = recognizer.record(source)
        return recognizer.recognize_google(recording, language=language).strip()
    except speech.UnknownValueError as error:
        raise ValueError("I couldn't understand that recording. Try again in a quiet place or type your answer.") from error
    except speech.RequestError as error:
        raise RuntimeError(
            "Speech-to-text could not connect. Check your internet connection, then try again or type your answer."
        ) from error


def interviewer_voice_button(text, language):
    """Show an in-browser play button for an interviewer message."""
    safe_text = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
    safe_language = html.escape(language, quote=True)
    components.html(
        f"""
        <button id="play-interviewer-voice" style="border:0;border-radius:10px;padding:10px 15px;
            background:#edf2ff;color:#3449b8;font:600 14px system-ui;cursor:pointer">
            🔊 Hear interviewer
        </button>
        <script>
        const playButton = document.getElementById("play-interviewer-voice");
        playButton.addEventListener("click", () => {{
            if (!("speechSynthesis" in window)) {{
                playButton.textContent = "Voice playback is unavailable in this browser";
                return;
            }}
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance({safe_text});
            utterance.lang = "{safe_language}";
            utterance.rate = 0.95;
            window.speechSynthesis.speak(utterance);
        }});
        </script>
        """,
        height=52,
        scrolling=False,
    )


def generate_interview_question(interview):
    next_number = interview["questions_asked"] + 1
    instructions = (
        "You are a realistic but supportive interviewer for a student candidate. "
        f"Target role: {interview['target_role']}. Interview style: {interview['interview_type']}. "
        f"Difficulty: {interview['difficulty']}. You are asking question {next_number} "
        f"of {interview['question_count']}. Ask exactly one concise, relevant question. "
        "Adapt it to the candidate's last answer when useful, otherwise move to a fresh interview topic. "
        "Do not answer the question, grade the candidate, or include multiple questions."
    )
    messages = [{"role": "system", "content": instructions}, *interview["messages"]]
    if not interview["messages"]:
        messages.append({"role": "user", "content": "Start the interview with the first question now."})
    response = ollama_chat(messages, num_predict=180)
    interview["messages"].append({"role": "assistant", "content": response})
    interview["questions_asked"] = next_number


def generate_interview_feedback(interview):
    instructions = (
        "You are an experienced interviewer giving a fair practice debrief to a student. "
        f"Assess this {interview['difficulty'].lower()} {interview['interview_type'].lower()} interview "
        f"for the role of {interview['target_role']}. Use only the answers in the conversation. "
        "Give concise sections titled: Readiness score (0-100, approximate), Strengths, "
        "What to improve, Answer-by-answer notes, and One practice goal. "
        "Be specific, constructive and honest; do not claim uncertain facts are correct. "
        "If the interview ended early, make that clear and assess only the answers given."
    )
    feedback = ollama_chat(
        [{"role": "system", "content": instructions}, *interview["messages"]],
        num_predict=700,
    )
    interview["messages"].append({"role": "assistant", "content": feedback})
    interview["feedback"] = feedback
    interview["completed"] = True
    interview["active"] = False


def advance_interview(interview, user_id):
    """Generate the next question or the debrief after an answer/finish request."""
    if interview.get("finish_early") or interview["answers_given"] >= interview["question_count"]:
        generate_interview_feedback(interview)
    else:
        generate_interview_question(interview)
    interview["awaiting_ai"] = False
    interview["last_error"] = None
    if interview["completed"] and not interview.get("saved"):
        store_completed_interview(interview, user_id)


def submit_interview_answer(interview, user_id, answer):
    """Add a typed or transcribed answer and request the next interview turn."""
    interview["messages"].append({"role": "user", "content": answer.strip()})
    interview["answers_given"] += 1
    interview["awaiting_ai"] = True
    interview["finish_early"] = False
    interview["last_error"] = None
    try:
        with st.spinner("Your interviewer is considering your answer..."):
            advance_interview(interview, user_id)
    except Exception as error:
        interview["last_error"] = ollama_error_message(error)
    st.session_state.live_interview = interview


def store_completed_interview(interview, user_id):
    """Persist a completed session once, keeping its feedback if storage fails."""
    if interview.get("saved"):
        return
    interview.setdefault("completed_at", datetime.now().isoformat(timespec="seconds"))
    try:
        interview["history_id"] = save_interview_session(
            user_id,
            interview["target_role"],
            interview["interview_type"],
            interview["difficulty"],
            interview["question_count"],
            interview["answers_given"],
            json.dumps(interview["messages"], ensure_ascii=False),
            interview["feedback"],
            interview["completed_at"],
        )
    except Exception as error:
        interview["save_error"] = str(error)
    else:
        interview["saved"] = True
        interview.pop("save_error", None)


def ollama_error_message(error):
    if isinstance(error, HTTPError):
        model_name = setting("OLLAMA_MODEL", "gemma3:1b").strip()
        if error.code == 404:
            return f"Ollama could not find the selected model. Run `ollama run {model_name}` in PowerShell, then retry."
        return f"Ollama returned an HTTP {error.code} error. Check the model and Ollama server settings."
    if isinstance(error, URLError):
        return "Could not reach Ollama. Open the Ollama app and run the selected model in PowerShell, then retry."
    return f"The AI request failed: {error}"


def send_verification_email(recipient, code, purpose="signup"):
    """Send a short-lived signup or password-reset code with Brevo."""
    api_key = setting("BREVO_API_KEY").strip()
    sender_email = setting("BREVO_SENDER_EMAIL").strip()
    sender_name = setting("BREVO_SENDER_NAME", "Interview Prep Portal").strip()
    if not api_key or not sender_email:
        raise ValueError(
            "Email verification is not configured. Add BREVO_API_KEY and "
            "BREVO_SENDER_EMAIL to .streamlit/secrets.toml."
        )

    is_password_reset = purpose == "password reset"
    action = "reset your password" if is_password_reset else "finish creating your account"
    subject = "Your Interview Prep Portal password reset code" if is_password_reset else "Your Interview Prep Portal verification code"
    body = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": (
            f"Use this code to {action}: {code}. It expires in 10 minutes. "
            "If you did not request this code, you can ignore this email."
        ),
        "htmlContent": (
            f"<p>Use this code to {action} in Interview Prep Portal:</p>"
            f"<p style=\"font-size:28px;font-weight:bold;letter-spacing:6px\">{code}</p>"
            "<p>This code expires in 10 minutes. If you did not request it, ignore this email.</p>"
        ),
    }
    request = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            response.read()
    except HTTPError as error:
        try:
            details = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            details = {}
        message = details.get("message", "The email provider rejected the request.")
        raise RuntimeError(f"Brevo could not send the email: {message}") from None
    except URLError as error:
        raise RuntimeError(f"Could not connect to the email service: {error.reason}") from None


def masked_email(email):
    local_part, _, domain = email.partition("@")
    visible = local_part[:1] if local_part else ""
    return f"{visible}{'•' * max(2, len(local_part) - 1)}@{domain}"


st.set_page_config(page_title="Interview Prep Portal", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    :root { --ink:#172443; --muted:#71809b; --primary:#5368e8; --line:#e5eaf3; --surface:#fff; }
    html, body, [class*="css"] { font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    div[data-testid="stAppViewContainer"] { position:relative; isolation:isolate; background:#f5f7fc; color:var(--ink); }
    div[data-testid="stAppViewContainer"]::before { content:""; position:fixed; inset:-7vh -4vw; z-index:0; pointer-events:none; opacity:.78; background:radial-gradient(ellipse at 14% 20%,rgba(83,104,232,.14),transparent 28%),radial-gradient(ellipse at 86% 26%,rgba(57,203,183,.14),transparent 25%),radial-gradient(ellipse at 72% 88%,rgba(83,104,232,.10),transparent 24%),radial-gradient(circle,rgba(83,104,232,.22) 1px,transparent 1.6px); background-size:100% 100%,100% 100%,100% 100%,34px 34px; animation:portalDrift 28s ease-in-out infinite alternate; }
    div[data-testid="stAppViewContainer"]::after { content:""; position:fixed; width:210px; height:210px; right:5vw; top:14vh; z-index:0; pointer-events:none; border:1px solid rgba(83,104,232,.12); border-radius:50%; box-shadow:0 0 0 22px rgba(83,104,232,.035),0 0 0 48px rgba(57,203,183,.025); animation:portalOrbit 19s ease-in-out infinite alternate; }
    @keyframes portalDrift { from { transform:translate3d(-.7%,-.5%,0) scale(1); } to { transform:translate3d(.7%,.6%,0) scale(1.035); } }
    @keyframes portalOrbit { from { transform:translate3d(0,-8px,0) rotate(-7deg); } to { transform:translate3d(-12px,13px,0) rotate(8deg); } }
    div[data-testid="stMain"], section.main { position:relative; z-index:1; }
    div[data-testid="stHeader"] { position:relative; z-index:2; background:rgba(245,247,252,.86); }
    .block-container { max-width:1240px; padding-top:2rem; padding-bottom:3rem; }
    section[data-testid="stSidebar"] { position:relative; z-index:2; background:#101c37; }
    section[data-testid="stSidebar"] > div { background:linear-gradient(180deg,#142343 0%,#101a32 100%); }
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 { color:#eef3ff; }
    section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] { color:#aab6d0; }
    section[data-testid="stSidebar"] div[role="radiogroup"] { gap:.35rem; }
    section[data-testid="stSidebar"] div[role="radiogroup"] label { padding:.55rem .65rem; border-radius:12px; transition:background .18s ease; }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover,
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:rgba(115,137,255,.19); }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color:#fff; font-weight:700; }
    .sidebar-brand { display:flex; align-items:center; gap:.7rem; padding:.5rem .15rem 1.35rem; color:#fff; font-size:1.05rem; font-weight:800; }
    .sidebar-brand .brand-icon { width:2.55rem; height:2.55rem; display:grid; place-items:center; border-radius:13px; background:linear-gradient(135deg,#6f7eff,#40d7c2); font-size:1.3rem; }
    .sidebar-brand small { display:block; color:#aab6d0; font-size:.64rem; font-weight:600; letter-spacing:.13em; margin-top:.1rem; }
    .profile-card { display:flex; align-items:center; gap:.7rem; padding:.8rem; margin:.1rem 0 1.15rem; border:1px solid rgba(207,219,255,.13); background:rgba(255,255,255,.06); border-radius:15px; color:#fff; }
    .profile-avatar { width:2.35rem; height:2.35rem; border-radius:50%; display:grid; place-items:center; flex:0 0 auto; background:#394d7b; color:#dce6ff; font-weight:800; }
    .profile-card small { display:block; margin-top:.15rem; color:#aab6d0; font-size:.76rem; }
    .page-hero { position:relative; overflow:hidden; display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.65rem 2rem; margin:0 0 1.4rem; border-radius:23px; color:#fff; background:linear-gradient(112deg,#17274a 0%,#263f78 62%,#4258b8 100%); box-shadow:0 14px 34px rgba(32,54,105,.15); }
    .page-hero:after { content:""; position:absolute; width:220px; height:220px; right:9%; top:-135px; border:1px solid rgba(255,255,255,.15); border-radius:50%; box-shadow:0 0 0 26px rgba(255,255,255,.035),0 0 0 54px rgba(255,255,255,.025); }
    .page-hero .eyebrow { margin:0 0 .4rem; color:#aebeff; font-size:.7rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase; }
    .page-hero h1 { position:relative; z-index:1; margin:0; color:#fff; font-size:1.75rem; line-height:1.25; font-weight:800; letter-spacing:-.035em; }
    .page-hero .hero-copy { position:relative; z-index:1; margin:.45rem 0 0; color:#d7e1ff; font-size:.96rem; }
    .hero-mark { position:relative; z-index:1; display:grid; place-items:center; width:3.5rem; height:3.5rem; border:1px solid rgba(255,255,255,.18); border-radius:18px; background:rgba(255,255,255,.11); font-size:1.65rem; flex:0 0 auto; }
    h2, h3 { color:var(--ink); letter-spacing:-.025em; }
    div[data-testid="stMetric"] { padding:1rem 1.15rem; background:var(--surface); border:1px solid var(--line); border-radius:17px; box-shadow:0 5px 17px rgba(31,47,87,.045); }
    div[data-testid="stMetricLabel"] { color:var(--muted); font-size:.86rem; font-weight:600; }
    div[data-testid="stMetricValue"] { color:var(--ink); font-weight:800; letter-spacing:-.04em; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; border-radius:17px !important; background:#fff; box-shadow:0 5px 18px rgba(31,47,87,.04); }
    div.stButton > button, div.stFormSubmitButton > button { min-height:2.7rem; border-radius:11px; font-weight:700; transition:transform .16s ease,box-shadow .16s ease; }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover { transform:translateY(-1px); box-shadow:0 7px 16px rgba(69,91,191,.14); }
    button[data-testid="stBaseButton-primary"] { border:0; background:linear-gradient(110deg,#5368e8,#6e73ed); color:#fff; }
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, div[data-baseweb="select"] > div { border-radius:10px; }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus { border-color:#8290f3; box-shadow:0 0 0 2px rgba(83,104,232,.12); }
    div[data-testid="stAlert"] { border-radius:13px; }
    div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
    .stTabs [data-baseweb="tab-list"] { gap:.5rem; border-bottom:1px solid var(--line); }
    .stTabs [data-baseweb="tab"] { padding:.65rem 1rem; border-radius:10px 10px 0 0; color:var(--muted); font-weight:650; }
    .stTabs [aria-selected="true"] { color:var(--primary) !important; }
    .auth-welcome { padding:1.5rem 1.3rem; }
    .auth-icon { display:grid; place-items:center; width:3.6rem; height:3.6rem; margin-bottom:1.2rem; border-radius:19px; background:linear-gradient(135deg,#6577f5,#39cbb7); color:#fff; font-size:1.7rem; box-shadow:0 9px 22px rgba(83,104,232,.23); }
    .auth-welcome .auth-kicker { color:#5368e8; font-size:.72rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase; }
    .auth-welcome h1 { margin:.5rem 0 .6rem; color:#172443; font-size:2.45rem; line-height:1.12; letter-spacing:-.05em; }
    .auth-welcome p { color:#71809b; font-size:1rem; line-height:1.7; }
    .auth-note { margin-top:1.4rem; padding:1rem 1.1rem; border:1px solid #dce5ff; border-radius:14px; background:#edf2ff; color:#34466f; line-height:1.6; }
    .question-meta { display:flex; align-items:center; justify-content:space-between; gap:.7rem; margin-bottom:.55rem; }
    .topic-chip { display:inline-block; padding:.28rem .65rem; border-radius:999px; background:#edf2ff; color:#4357c6; font-size:.76rem; font-weight:750; }
    .question-number { color:#98a3b8; font-size:.72rem; font-weight:750; letter-spacing:.08em; text-transform:uppercase; }
    .result-count { display:inline-block; padding:.42rem .75rem; margin:.3rem 0 .7rem; border-radius:999px; background:#e8f8f5; color:#167e72; font-size:.8rem; font-weight:750; }
    @media (prefers-reduced-motion: reduce) { div[data-testid="stAppViewContainer"]::before, div[data-testid="stAppViewContainer"]::after { animation:none !important; } }
    @media (max-width:700px) { .block-container{padding-top:1rem;} .page-hero{padding:1.25rem 1.3rem;border-radius:18px;} .page-hero h1{font-size:1.4rem;} .hero-mark{width:2.8rem;height:2.8rem;} .auth-welcome h1{font-size:2rem;} }
    </style>
    """,
    unsafe_allow_html=True,
)


def page_header(eyebrow, title, description, icon):
    st.markdown(
        f"""
        <div class="page-hero">
            <div>
                <p class="eyebrow">{eyebrow}</p>
                <h1>{icon} {title}</h1>
                <p class="hero-copy">{description}</p>
            </div>
            <div class="hero-mark">{icon}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def open_topic_practice(topic):
    """Navigate from the study plan to focused practice for one topic."""
    st.session_state["practice_focus_topic"] = topic
    st.session_state["nav_page"] = "🧩  Question Bank"


init_db()

if "user" not in st.session_state:
    left, right = st.columns([1.05, .95], gap="large")
    with left:
        st.markdown(
            """
            <div class="auth-welcome">
                <div class="auth-icon">🎯</div>
                <div class="auth-kicker">Your interview practice space</div>
                <h1>Prepare with<br>purpose.</h1>
                <p>Build confidence one question at a time. Practise by topic, take timed mock tests, and keep track of your progress.</p>
                <div class="auth-note"><strong>✨ Learn · Practise · Improve</strong><br>Save questions, get local AI coaching, and see how far you have come.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        with st.container(border=True):
            st.markdown("### Welcome to your portal")
            st.caption("Sign in to continue, or create a student account.")
            login_tab, register_tab = st.tabs(["🔐  Login", "✨  Create account"])

            with login_tab:
                with st.form("login_form"):
                    login_name = st.text_input("Username", key="login_username")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    login_clicked = st.form_submit_button("Login to portal", type="primary", use_container_width=True)
                if login_clicked:
                    account = authenticate_user(login_name, login_password)
                    if account:
                        st.session_state.user = account
                        st.rerun()
                    st.error("Username or password is incorrect.")

                if st.session_state.pop("password_reset_success", False):
                    st.success("Password updated. Log in with your username and new password.")

                reset_pending = st.session_state.get("password_reset_pending")
                with st.expander("Forgot password? Reset it with your email", expanded=bool(reset_pending)):
                    reset_pending = st.session_state.get("password_reset_pending")
                    now = time.time()
                    if reset_pending and now >= reset_pending["expires_at"]:
                        st.session_state.pop("password_reset_pending", None)
                        reset_pending = None
                        st.warning("That reset code expired. Request a new one to continue.")

                    if reset_pending:
                        st.caption("Enter the 6-digit code from your email and choose a new password. The code expires in 10 minutes.")
                        with st.form("password_reset_form"):
                            reset_code = st.text_input("Email code", max_chars=6, placeholder="000000", key="password_reset_code")
                            reset_password = st.text_input("New password (at least 8 characters)", type="password", key="password_reset_new_password")
                            reset_confirm = st.text_input("Confirm new password", type="password", key="password_reset_confirm_password")
                            reset_clicked = st.form_submit_button("Reset password", type="primary", width="stretch")
                        if reset_clicked:
                            if not reset_code.isdigit() or len(reset_code) != 6:
                                st.error("Enter the 6-digit code from your email.")
                            elif reset_pending["attempts"] >= 5:
                                st.session_state.pop("password_reset_pending", None)
                                st.error("Too many incorrect code attempts. Start the reset again.")
                            elif not secrets.compare_digest(reset_code, reset_pending["code"]):
                                reset_pending["attempts"] += 1
                                if reset_pending["attempts"] >= 5:
                                    st.session_state.pop("password_reset_pending", None)
                                    st.error("Too many incorrect code attempts. Start the reset again.")
                                else:
                                    st.session_state.password_reset_pending = reset_pending
                                    st.error(f"That code is incorrect. {5 - reset_pending['attempts']} attempt(s) remaining.")
                            elif reset_pending["user_id"] is None:
                                st.error("That code is invalid or expired. Request a new reset code.")
                            elif len(reset_password) < 8:
                                st.error("Choose a password with at least 8 characters.")
                            elif reset_password != reset_confirm:
                                st.error("The passwords do not match.")
                            elif not update_user_password(reset_pending["user_id"], reset_password):
                                st.session_state.pop("password_reset_pending", None)
                                st.error("That account could not be updated. Start the reset again.")
                            else:
                                st.session_state.pop("password_reset_pending", None)
                                st.session_state.password_reset_success = True
                                st.rerun()

                        cooldown = 60 - int(time.time() - reset_pending["sent_at"])
                        resend_limit_reached = reset_pending["send_count"] >= 4
                        if st.button("Resend reset code", disabled=cooldown > 0 or resend_limit_reached, key="resend_password_reset_code"):
                            new_code = f"{secrets.randbelow(1_000_000):06d}"
                            try:
                                if reset_pending["user_id"] is not None:
                                    send_verification_email(reset_pending["email"], new_code, purpose="password reset")
                            except Exception as error:
                                st.error(f"Could not resend the reset email. Check your Brevo sender and API settings. {error}")
                            else:
                                reset_pending.update({
                                    "code": new_code,
                                    "expires_at": time.time() + 600,
                                    "sent_at": time.time(),
                                    "attempts": 0,
                                    "send_count": reset_pending["send_count"] + 1,
                                })
                                st.session_state.password_reset_pending = reset_pending
                                st.info("If a matching account exists, a new code has been sent. Check your inbox and spam folder.")
                        if cooldown > 0 and not resend_limit_reached:
                            st.caption(f"You can request another code in {cooldown} seconds.")
                        elif resend_limit_reached:
                            st.caption("You have reached the resend limit. Start a new reset request later.")
                        if st.button("Use a different email", key="cancel_password_reset"):
                            st.session_state.pop("password_reset_pending", None)
                            st.rerun()
                    else:
                        with st.form("request_password_reset_form"):
                            reset_email = st.text_input("Account email address", placeholder="you@example.com", key="password_reset_email")
                            request_reset_clicked = st.form_submit_button("Send reset code", type="primary", width="stretch")
                        if request_reset_clicked:
                            normalized_email = reset_email.strip().lower()
                            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
                                st.error("Enter a valid email address.")
                            else:
                                account = get_account_by_email(normalized_email)
                                code = f"{secrets.randbelow(1_000_000):06d}"
                                try:
                                    if account:
                                        send_verification_email(normalized_email, code, purpose="password reset")
                                except Exception as error:
                                    st.error(f"Could not send the reset email. Check your Brevo sender and API settings. {error}")
                                else:
                                    st.session_state.password_reset_pending = {
                                        "email": normalized_email,
                                        "user_id": account["id"] if account else None,
                                        "code": code,
                                        "expires_at": time.time() + 600,
                                        "sent_at": time.time(),
                                        "attempts": 0,
                                        "send_count": 1,
                                    }
                                    st.info("If a matching account exists, a reset code has been sent. Check your inbox and spam folder.")
                                    st.rerun()

            with register_tab:
                st.caption("Verify your email address first, then create your account password.")
                pending = st.session_state.get("email_signup_pending")
                verified = st.session_state.get("email_signup_verified")
                now = time.time()
                if pending and now >= pending["expires_at"]:
                    st.session_state.pop("email_signup_pending", None)
                    pending = None
                    st.warning("That verification request expired. Start signup again to request a new code.")
                if verified and now - verified["verified_at"] > 600:
                    st.session_state.pop("email_signup_verified", None)
                    st.session_state.pop("verified_register_password", None)
                    st.session_state.pop("verified_confirm_password", None)
                    verified = None
                    st.warning("Email verification timed out. Please start signup again.")

                if verified:
                    st.success(f"Email verified: {masked_email(verified['email'])}")
                    with st.form("finish_signup_form"):
                        new_password = st.text_input("Choose a password (at least 8 characters)", type="password", key="verified_register_password")
                        confirm_password = st.text_input("Confirm password", type="password", key="verified_confirm_password")
                        register_clicked = st.form_submit_button("Create my account", type="primary", use_container_width=True)
                    if register_clicked:
                        if len(new_password) < 8:
                            st.error("Choose a password with at least 8 characters.")
                        elif new_password != confirm_password:
                            st.error("The passwords do not match.")
                        else:
                            account, error = register_user(verified["username"], new_password, email=verified["email"])
                            if error:
                                st.error(error)
                            else:
                                st.session_state.pop("email_signup_verified", None)
                                st.session_state.pop("verified_register_password", None)
                                st.session_state.pop("verified_confirm_password", None)
                                st.session_state.user = account
                                st.success(f"Account created. Your role is {account['role']}.")
                                st.rerun()
                    if st.button("Start over", key="cancel_verified_signup"):
                        st.session_state.pop("email_signup_verified", None)
                        st.session_state.pop("verified_register_password", None)
                        st.session_state.pop("verified_confirm_password", None)
                        st.rerun()

                elif pending:
                    st.info(f"Enter the 6-digit code sent to {masked_email(pending['email'])}. It expires in about 10 minutes.")
                    with st.form("verify_signup_email_form"):
                        entered_code = st.text_input("Email verification code", max_chars=6, placeholder="000000")
                        verify_clicked = st.form_submit_button("Verify email address", type="primary", use_container_width=True)
                    if verify_clicked:
                        if not entered_code.isdigit() or len(entered_code) != 6:
                            st.error("Enter the 6-digit code from your email.")
                        elif pending["attempts"] >= 5:
                            st.session_state.pop("email_signup_pending", None)
                            st.error("Too many incorrect attempts. Start signup again to request a new code.")
                        else:
                            pending["attempts"] += 1
                            st.session_state.email_signup_pending = pending
                            if secrets.compare_digest(entered_code, pending["code"]):
                                st.session_state.email_signup_verified = {
                                    "username": pending["username"],
                                    "email": pending["email"],
                                    "verified_at": time.time(),
                                }
                                st.session_state.pop("email_signup_pending", None)
                                st.rerun()
                            else:
                                remaining = 5 - pending["attempts"]
                                st.error(f"That code did not match. {remaining} attempt(s) remaining.")

                    cooldown = 60 - int(time.time() - pending["sent_at"])
                    resend_limit_reached = pending["send_count"] >= 4
                    if st.button("Resend code", disabled=cooldown > 0 or resend_limit_reached, key="resend_signup_email_code"):
                        new_code = f"{secrets.randbelow(1_000_000):06d}"
                        try:
                            send_verification_email(pending["email"], new_code)
                        except Exception as error:
                            st.error(f"Could not resend the verification email. Check your Brevo sender and API settings. {error}")
                        else:
                            pending.update({
                                "code": new_code,
                                "expires_at": time.time() + 600,
                                "sent_at": time.time(),
                                "attempts": 0,
                                "send_count": pending["send_count"] + 1,
                            })
                            st.session_state.email_signup_pending = pending
                            st.success("A new verification email has been sent.")
                    if cooldown > 0 and not resend_limit_reached:
                        st.caption(f"You can request another code in {cooldown} seconds.")
                    elif resend_limit_reached:
                        st.caption("You have reached the resend limit. Start over to try again.")
                    if st.button("Use a different email address", key="cancel_pending_email_signup"):
                        st.session_state.pop("email_signup_pending", None)
                        st.rerun()

                else:
                    with st.form("request_signup_email_code_form"):
                        new_name = st.text_input("Choose a username", key="signup_username")
                        new_email = st.text_input("Email address", key="signup_email", placeholder="you@example.com")
                        request_code_clicked = st.form_submit_button("Send verification code", type="primary", use_container_width=True)
                    if request_code_clicked:
                        normalized_email = new_email.strip().lower()
                        if len(new_name.strip()) < 3 or not new_name.strip().replace("_", "").isalnum():
                            st.error("Username must be at least 3 characters and use only letters, numbers or underscores.")
                        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
                            st.error("Enter a valid email address.")
                        elif username_exists(new_name):
                            st.error("That username is already taken.")
                        elif email_in_use(normalized_email):
                            st.error("That email address is already linked to an account.")
                        else:
                            code = f"{secrets.randbelow(1_000_000):06d}"
                            try:
                                send_verification_email(normalized_email, code)
                            except Exception as error:
                                st.error(f"Could not send the verification email. Check your Brevo sender and API settings. {error}")
                            else:
                                st.session_state.email_signup_pending = {
                                    "username": new_name.strip(),
                                    "email": normalized_email,
                                    "code": code,
                                    "expires_at": time.time() + 600,
                                    "sent_at": time.time(),
                                    "attempts": 0,
                                    "send_count": 1,
                                }
                                st.rerun()
            st.caption("The first account created becomes the demo admin. Other accounts are students.")
    st.stop()

user = st.session_state.user
safe_username = html.escape(user["username"])
st.sidebar.markdown(
    '<div class="sidebar-brand"><span class="brand-icon">🎯</span><span>PrepMate<small>INTERVIEW PORTAL</small></span></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f'<div class="profile-card"><span class="profile-avatar">{safe_username[:1].upper()}</span><span>Signed in as<br><strong>{safe_username}</strong><small>{user["role"].title()} account</small></span></div>',
    unsafe_allow_html=True,
)
if st.sidebar.button("↪  Log out", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()
page_labels = {
    "📊  Dashboard": "Dashboard",
    "🧩  Question Bank": "Question Bank",
    "🔖  Bookmarks": "Bookmarks",
    "⏱️  Mock Test": "Mock Test",
    "🤖  AI Interview Coach": "AI Interview Coach",
    "🎙️  AI Interviewer": "AI Interviewer",
}
if user["role"] == "admin":
    page_labels["🛠️  Manage Questions"] = "Manage Questions"
selected_page = st.sidebar.radio("YOUR SPACE", list(page_labels), key="nav_page")
page = page_labels[selected_page]

if page == "Dashboard":
    page_header("YOUR LEARNING OVERVIEW", "Dashboard", "A clear view of your practice, progress and next steps.", "📊")
    stats = get_dashboard(user["id"])
    a, b, c, d = st.columns(4)
    a.metric("🧩  Questions", stats["question_count"])
    b.metric("⏱️  Tests completed", stats["attempt_count"])
    c.metric("📈  Average score", f'{stats["average_score"]:.0f}%')
    d.metric("🔖  Bookmarked", stats["bookmark_count"])
    recent_column, trend_column = st.columns([1.2, .8], gap="large")
    recent = stats["recent"]
    with recent_column:
        st.subheader("🗂️  Recent mock tests")
        if recent:
            df = pd.DataFrame(recent, columns=["Date", "Topic", "Score (%)", "Correct", "Total"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Complete your first mock test to start building a progress history.")
    with trend_column:
        st.subheader("📈  Score trend")
        if recent:
            st.line_chart(df.set_index("Date")["Score (%)"], height=250)
        else:
            with st.container(border=True):
                st.markdown("### Your progress starts here")
                st.write("Take a short mock test to create your first score and track improvement over time.")
    st.subheader("🎯 Your personalized study plan")
    topic_performance = stats["topic_performance"]
    if topic_performance:
        weakest_topic = topic_performance[0]
        with st.container(border=True):
            focus_column, metrics_column = st.columns([1.5, 1], gap="large")
            with focus_column:
                st.markdown(f"### Focus next: {html.escape(weakest_topic['topic'])}")
                st.write(
                    f"This is your lowest-scoring topic across your last "
                    f"{weakest_topic['attempt_count']} topic-focused mock test(s)."
                )
                st.progress(weakest_topic["accuracy"], text=f"Recent accuracy: {weakest_topic['accuracy']}%")
                st.button(
                    f"Practise {weakest_topic['topic']} questions",
                    type="primary",
                    key="study_plan_practice",
                    on_click=open_topic_practice,
                    args=(weakest_topic["topic"],),
                )
            with metrics_column:
                st.metric("Questions attempted", weakest_topic["total"])
                st.metric("Correct answers", weakest_topic["correct"])
        performance_table = pd.DataFrame([
            {
                "Topic": item["topic"],
                "Recent accuracy (%)": item["accuracy"],
                "Focused tests": item["attempt_count"],
            }
            for item in topic_performance
        ])
        st.dataframe(performance_table, hide_index=True, use_container_width=True)
        st.caption("Topic accuracy uses up to your three latest topic-focused mock tests. Mixed-topic tests are not used for this recommendation.")
    else:
        with st.container(border=True):
            st.markdown("### Your personalized focus will appear here")
            st.write("Take a mock test for a specific topic to get a score-based recommendation. Mixed-topic tests do not identify a weak topic.")
    st.subheader("A simple study rhythm")
    plan_columns = st.columns(3, gap="medium")
    study_steps = [
        ("01", "Choose a topic", "Start with one area you want to strengthen."),
        ("02", "Practise and save", "Review explanations and bookmark tricky questions."),
        ("03", "Check your progress", "Use a timed test to measure what you remember."),
    ]
    for column, (number, title, description) in zip(plan_columns, study_steps):
        with column:
            with st.container(border=True):
                st.caption(f"STEP {number}")
                st.markdown(f"#### {title}")
                st.write(description)

elif page == "Question Bank":
    page_header("PRACTICE LIBRARY", "Question Bank", "Find a topic, sharpen your answers and save questions for later.", "🧩")
    all_questions = get_questions()
    topics = ["All topics"] + sorted({q["topic"] for q in all_questions})
    focus_topic = st.session_state.pop("practice_focus_topic", None)
    focus_notice = None
    if focus_topic in topics:
        st.session_state["question_bank_topic"] = focus_topic
        focus_notice = focus_topic
    with st.container(border=True):
        col1, col2 = st.columns([1, 2])
        topic = col1.selectbox("Filter by topic", topics, key="question_bank_topic")
        query = col2.text_input("Search the question bank", placeholder="Try a keyword, topic, or concept")
    if focus_notice:
        st.success(f"Study plan selected **{focus_notice}**. Start with these questions and check your progress in the next mock test.")
    selected = [q for q in all_questions if (topic == "All topics" or q["topic"] == topic)
                and query.lower() in (q["question"] + q["topic"]).lower()]
    st.markdown(f'<span class="result-count">{len(selected)} questions found</span>', unsafe_allow_html=True)
    bookmarks = get_bookmarks(user["id"])
    for index, q in enumerate(selected, start=1):
        with st.container(border=True):
            st.markdown(
                f'<div class="question-meta"><span class="topic-chip">{html.escape(q["topic"])}</span><span class="question-number">QUESTION {index:02d}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"#### {html.escape(q['question'])}")
            choice = st.radio(
                "Choose an answer", q["options"], index=None,
                key=f"practice_v2_{q['id']}", label_visibility="collapsed",
            )
            left, right = st.columns([1, 3])
            if left.button("Check answer", key=f"check_{q['id']}", disabled=choice is None):
                if choice == q["answer"]:
                    st.success("Correct!")
                else:
                    st.error(f"Not quite. Correct answer: {q['answer']}")
                st.write(q["explanation"])
            is_saved = q["id"] in bookmarks
            if right.button("★ Remove bookmark" if is_saved else "☆ Bookmark", key=f"bookmark_{q['id']}"):
                set_bookmark(q["id"], not is_saved, user["id"])
                st.rerun()

elif page == "Bookmarks":
    page_header("YOUR REVISION LIST", "Bookmarks", "Keep the questions you want to revisit close at hand.", "🔖")
    saved = [q for q in get_questions() if q["id"] in get_bookmarks(user["id"])]
    if not saved:
        st.info("Your bookmark list is empty. Save a question from the Question Bank when you want to review it later.")
    for index, q in enumerate(saved, start=1):
        with st.container(border=True):
            st.markdown(
                f'<div class="question-meta"><span class="topic-chip">{html.escape(q["topic"])}</span><span class="question-number">SAVED {index:02d}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"#### {html.escape(q['question'])}")
            st.write(f"**Answer:** {q['answer']}  \n{q['explanation']}")
            if st.button("Remove bookmark", key=f"remove_{q['id']}"):
                set_bookmark(q["id"], False, user["id"])
                st.rerun()

elif page == "AI Interview Coach":
    page_header("PERSONAL AI PRACTICE", "AI Interview Coach", "Get supportive feedback and shape a stronger interview answer.", "🤖")
    st.caption("Local feedback powered by Ollama on this computer. No OpenAI API key is needed.")
    form_column, tip_column = st.columns([1.5, .75], gap="large")
    with form_column:
        with st.container(border=True):
            st.markdown("### Tell us about your answer")
            with st.form("ai_feedback_form"):
                target_role = st.text_input("Target role", placeholder="e.g. Python developer")
                topic = st.text_input("Topic", placeholder="e.g. Python, SQL, communication")
                interview_question = st.text_area("Interview question", placeholder="What would the interviewer ask you?")
                candidate_answer = st.text_area("Your answer", height=180, placeholder="Write your answer as you would say it in an interview...")
                ask_ai = st.form_submit_button("✨  Get AI feedback", type="primary", use_container_width=True)
    with tip_column:
        with st.container(border=True):
            st.markdown("### A little coaching tip")
            st.write("Use a real example from a class project, assignment or team activity.")
            st.divider()
            st.markdown("**A strong answer often includes:**")
            st.markdown("- The situation or challenge\n- What you personally did\n- The result or lesson")
            st.caption("Keep personal or sensitive details out of your answer.")
    if ask_ai:
        if not interview_question.strip() or not candidate_answer.strip():
            st.warning("Enter both the interview question and your answer.")
        else:
            prompt = (
                f"Target role: {target_role.strip() or 'entry-level candidate'}\n"
                f"Topic: {topic.strip() or 'general interview'}\n"
                f"Interview question: {interview_question.strip()}\n"
                f"Candidate answer: {candidate_answer.strip()}"
            )
            instructions = (
                "You are a supportive interview coach. Give concise, constructive feedback in four sections: "
                "What worked, What to improve, A stronger sample answer, and One follow-up question. "
                "Do not claim an answer is factually correct when uncertain. Keep the sample answer realistic for a student."
            )
            with st.spinner("Reviewing your answer..."):
                try:
                    feedback = ollama_chat(
                        [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
                        num_predict=600,
                    )
                    st.markdown(feedback)
                except Exception as error:
                    st.error(ollama_error_message(error))

elif page == "AI Interviewer":
    page_header("LIVE PRACTICE", "AI Interviewer", "Practise a spoken or typed interview, then get a personal debrief.", "🎙️")
    st.caption(
        "AI questions and feedback use your configured Ollama model. In voice mode, the browser reads questions aloud and "
        "recorded answers are transcribed by Google's public speech service, so internet is required. Audio is not saved to your "
        "interview history; the transcript is. Avoid sharing sensitive personal details."
    )
    interview = st.session_state.get("live_interview")

    if interview is None:
        with st.container(border=True):
            st.markdown("### Set up your interview")
            with st.form("live_interview_setup_form"):
                target_role = st.text_input("Target role", placeholder="e.g. Junior Python Developer")
                interview_type = st.selectbox("Interview style", ["Mixed", "Technical", "Behavioral"])
                difficulty = st.selectbox("Difficulty", ["Entry-level", "Intermediate", "Advanced"])
                question_count = st.selectbox("Questions", [3, 5, 8], index=1)
                voice_mode = st.checkbox("Enable voice mode: speak answers and hear questions", value=True)
                voice_language = st.selectbox(
                    "Voice language",
                    ["English (India)", "English (US)"],
                    disabled=not voice_mode,
                )
                start_interview = st.form_submit_button("Start interview", type="primary", width="stretch")
        if start_interview:
            interview = {
                "target_role": target_role.strip() or "Entry-level candidate",
                "interview_type": interview_type,
                "difficulty": difficulty,
                "question_count": question_count,
                "voice_mode": voice_mode,
                "voice_language": "en-IN" if voice_language == "English (India)" else "en-US",
                "session_key": secrets.token_hex(5),
                "questions_asked": 0,
                "answers_given": 0,
                "messages": [],
                "active": True,
                "completed": False,
                "awaiting_ai": True,
                "finish_early": False,
                "saved": False,
                "last_error": None,
            }
            with st.spinner("Your interviewer is preparing the first question..."):
                try:
                    generate_interview_question(interview)
                except Exception as error:
                    st.error(ollama_error_message(error))
                else:
                    interview["awaiting_ai"] = False
                    st.session_state.live_interview = interview
                    st.rerun()

        history = get_interview_history(user["id"])
        if history:
            st.subheader("🗂️  Previous interview debriefs")
            for past_interview in history:
                label = (
                    f"{past_interview['target_role']} · {past_interview['interview_type']} · "
                    f"{past_interview['completed_at']}"
                )
                with st.expander(label):
                    st.caption(
                        f"{past_interview['difficulty']} · "
                        f"{past_interview['answered_count']}/{past_interview['question_count']} answers"
                    )
                    st.markdown(past_interview["feedback"])

    elif interview["active"]:
        st.caption(
            f"{interview['target_role']} · {interview['interview_type']} · "
            f"{interview['difficulty']} · "
            f"{'Voice mode' if interview.get('voice_mode') else 'Text mode'}"
        )
        st.progress(
            interview["answers_given"] / interview["question_count"],
            text=f"Answers completed: {interview['answers_given']} / {interview['question_count']}",
        )
        if st.button(
            "Finish early and get feedback",
            disabled=interview["answers_given"] == 0 or interview["awaiting_ai"],
            key="finish_live_interview_early",
        ):
            interview["awaiting_ai"] = True
            interview["finish_early"] = True
            try:
                with st.spinner("Preparing your interview debrief..."):
                    advance_interview(interview, user["id"])
            except Exception as error:
                interview["last_error"] = ollama_error_message(error)
            st.session_state.live_interview = interview
            st.rerun()

        for message in interview["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if (
            interview.get("voice_mode")
            and interview["messages"]
            and interview["messages"][-1]["role"] == "assistant"
        ):
            interviewer_voice_button(
                interview["messages"][-1]["content"],
                interview.get("voice_language", "en-IN"),
            )

        if interview["awaiting_ai"]:
            if interview.get("last_error"):
                st.error(interview["last_error"])
            if st.button("Retry interviewer response", key="retry_live_interview_ai"):
                try:
                    with st.spinner("Your interviewer is responding..."):
                        advance_interview(interview, user["id"])
                except Exception as error:
                    interview["last_error"] = ollama_error_message(error)
                st.session_state.live_interview = interview
                st.rerun()
        else:
            if interview.get("voice_mode"):
                question_number = interview["questions_asked"]
                audio_value = st.audio_input(
                    "Record your answer",
                    sample_rate=16000,
                    key=f"interview_voice_{interview['session_key']}_{question_number}",
                    help="Record a short answer in English (ideally under a minute), then convert it to text so you can review it before sending.",
                )
                if audio_value:
                    st.audio(audio_value)
                    if st.button(
                        "Convert recording to text",
                        key=f"transcribe_interview_{interview['session_key']}_{question_number}",
                    ):
                        try:
                            with st.spinner("Transcribing your answer..."):
                                transcript = transcribe_voice_answer(
                                    audio_value.getvalue(),
                                    interview.get("voice_language", "en-IN"),
                                )
                            if not transcript:
                                st.warning("No words were detected. Record again or type your answer.")
                            else:
                                interview["draft_question"] = question_number
                                interview["draft_answer"] = transcript
                                st.session_state.live_interview = interview
                                st.rerun()
                        except (RuntimeError, ValueError) as error:
                            st.error(str(error))

                draft_key = f"interview_voice_draft_{interview['session_key']}_{question_number}"
                if interview.get("draft_question") == question_number:
                    if draft_key not in st.session_state:
                        st.session_state[draft_key] = interview.get("draft_answer", "")
                    reviewed_answer = st.text_area(
                        "Review or edit your transcript before sending",
                        key=draft_key,
                        height=120,
                    )
                    if st.button(
                        "Send spoken answer",
                        type="primary",
                        key=f"send_voice_interview_{interview['session_key']}_{question_number}",
                        disabled=not reviewed_answer.strip(),
                    ):
                        interview.pop("draft_question", None)
                        interview.pop("draft_answer", None)
                        submit_interview_answer(interview, user["id"], reviewed_answer)
                        st.rerun()

            answer = st.chat_input(
                "Or type your answer instead..." if interview.get("voice_mode") else "Type your answer to the interviewer...",
                key=f"interview_typed_{interview['session_key']}_{interview['questions_asked']}",
            )
            if answer and answer.strip():
                submit_interview_answer(interview, user["id"], answer)
                st.rerun()

    else:
        st.success("Interview complete. Review your debrief below, then start another practice interview when ready.")
        if interview.get("save_error"):
            st.warning("The debrief is ready, but it could not be saved to interview history.")
            if st.button("Retry saving interview history", key="retry_save_interview_history"):
                store_completed_interview(interview, user["id"])
                st.session_state.live_interview = interview
                st.rerun()
        for message in interview["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        if st.button("Start another interview", type="primary", key="start_another_live_interview"):
            st.session_state.pop("live_interview", None)
            st.rerun()

elif page == "Manage Questions":
    if user["role"] != "admin":
        st.error("Only the demo admin can manage the shared question bank.")
        st.stop()
    page_header("ADMIN WORKSPACE", "Manage Questions", "Create, review, update and remove questions in the shared bank.", "🛠️")
    st.caption("Question bank management · Create · Read · Update · Delete")
    questions = get_questions()
    add_tab, edit_tab, delete_tab = st.tabs(["Create question", "Edit question", "Delete question"])

    with add_tab:
        with st.form("create_question_form"):
            topic = st.text_input("Topic", placeholder="e.g. Python, SQL, Networking")
            question_text = st.text_area("Question")
            a, b = st.columns(2)
            option_a = a.text_input("Option A")
            option_b = b.text_input("Option B")
            c, d = st.columns(2)
            option_c = c.text_input("Option C")
            option_d = d.text_input("Option D")
            answer_label = st.selectbox("Correct option", ["A", "B", "C", "D"])
            explanation = st.text_area("Explanation")
            create_clicked = st.form_submit_button("Add question", type="primary")
        if create_clicked:
            options = [option_a.strip(), option_b.strip(), option_c.strip(), option_d.strip()]
            if not topic.strip() or not question_text.strip() or not explanation.strip() or any(not value for value in options):
                st.error("Please fill in the topic, question, all four options and explanation.")
            elif len(set(options)) != 4:
                st.error("Each answer option must be different.")
            else:
                create_question(topic, question_text, options, options[ord(answer_label) - ord("A")], explanation)
                st.success("Question added to the database.")
                st.rerun()

    with edit_tab:
        if not questions:
            st.info("There are no questions to edit.")
        else:
            question_ids = [q["id"] for q in questions]
            question_by_id = {q["id"]: q for q in questions}
            selected_id = st.selectbox(
                "Choose question to edit",
                question_ids,
                format_func=lambda qid: f"#{qid} · {question_by_id[qid]['topic']} · {question_by_id[qid]['question'][:65]}",
                key="edit_question_id",
            )
            selected = question_by_id[selected_id]
            with st.form(f"edit_question_form_{selected_id}"):
                edit_topic = st.text_input("Topic", value=selected["topic"])
                edit_text = st.text_area("Question", value=selected["question"])
                a, b = st.columns(2)
                edit_a = a.text_input("Option A", value=selected["options"][0])
                edit_b = b.text_input("Option B", value=selected["options"][1])
                c, d = st.columns(2)
                edit_c = c.text_input("Option C", value=selected["options"][2])
                edit_d = d.text_input("Option D", value=selected["options"][3])
                edit_options = [edit_a, edit_b, edit_c, edit_d]
                old_answer_index = selected["options"].index(selected["answer"])
                edit_answer_label = st.selectbox("Correct option", ["A", "B", "C", "D"], index=old_answer_index)
                edit_explanation = st.text_area("Explanation", value=selected["explanation"])
                edit_clicked = st.form_submit_button("Save changes", type="primary")
            if edit_clicked:
                cleaned_options = [value.strip() for value in edit_options]
                if not edit_topic.strip() or not edit_text.strip() or not edit_explanation.strip() or any(not value for value in cleaned_options):
                    st.error("Please fill in every field before saving.")
                elif len(set(cleaned_options)) != 4:
                    st.error("Each answer option must be different.")
                else:
                    update_question(selected_id, edit_topic, edit_text, cleaned_options,
                                    cleaned_options[ord(edit_answer_label) - ord("A")], edit_explanation)
                    st.success("Question updated.")
                    st.rerun()

    with delete_tab:
        if not questions:
            st.info("There are no questions to delete.")
        else:
            selected_delete_id = st.selectbox(
                "Choose question to delete",
                [q["id"] for q in questions],
                format_func=lambda qid: f"#{qid} · {question_by_id[qid]['topic']} · {question_by_id[qid]['question'][:65]}",
                key="delete_question_id",
            )
            st.warning(f"This will permanently delete: {question_by_id[selected_delete_id]['question']}")
            confirm_delete = st.checkbox("I understand this question will be deleted.")
            if st.button("Delete selected question", disabled=not confirm_delete, type="primary"):
                delete_question(selected_delete_id)
                st.success("Question deleted.")
                st.rerun()

elif page == "Mock Test":
    page_header("TIMED PRACTICE", "Mock Test", "Choose your focus, set a pace and see how you perform.", "⏱️")
    all_questions = get_questions()
    if not all_questions:
        st.info("The question bank is empty. Ask the admin to add questions first.")
        st.stop()
    topics = ["All topics"] + sorted({q["topic"] for q in all_questions})
    if "test_active" not in st.session_state:
        st.session_state.test_active = False
    if not st.session_state.test_active:
        topic = st.selectbox("Choose topic", topics)
        topic_pool = [q for q in all_questions if topic == "All topics" or q["topic"] == topic]
        max_count = min(20, len(topic_pool))
        count = st.slider("Number of questions", 1, max_count, min(10, max_count))
        minutes = st.slider("Time limit (minutes)", 1, 20, 5)
        if st.button("Start mock test", type="primary"):
            st.session_state.test_questions = random.sample(topic_pool, count)
            st.session_state.test_topic = topic
            st.session_state.deadline = time.time() + minutes * 60
            st.session_state.test_active = True
            st.session_state.test_answers = {}
            st.rerun()
    if st.session_state.test_active:
        st_autorefresh(interval=1000, key="mock_test_clock")
        remaining = max(0, int(st.session_state.deadline - time.time()))
        st.metric("Time remaining", f"{remaining // 60:02d}:{remaining % 60:02d}")
        if remaining == 0:
            st.warning("Time is up. Submit to see your score.")
        with st.form("mock_form"):
            for index, q in enumerate(st.session_state.test_questions, 1):
                st.markdown(f"**{index}. {q['topic']}** — {q['question']}")
                answer = st.radio(
                    "Select one", q["options"], index=None,
                    key=f"mock_v2_{q['id']}", label_visibility="collapsed",
                )
                st.session_state.test_answers[q["id"]] = answer
            submitted = st.form_submit_button("Submit test", type="primary")
        if submitted or remaining == 0:
            questions = st.session_state.test_questions
            answers = {str(q["id"]): st.session_state.get(f"mock_v2_{q['id']}") for q in questions}
            correct = sum(answers[str(q["id"])] == q["answer"] for q in questions)
            score = round(correct * 100 / len(questions))
            add_attempt(st.session_state.test_topic, score, correct, len(questions), datetime.now().isoformat(timespec="seconds"), user["id"])
            st.session_state.last_result = (score, correct, len(questions), questions, answers)
            st.session_state.test_active = False
            st.rerun()
    if "last_result" in st.session_state and not st.session_state.test_active:
        score, correct, total, questions, answers = st.session_state.last_result
        st.success(f"Score: {score}% ({correct}/{total})")
        for q in questions:
            chosen = answers[str(q["id"])]
            status = "Correct" if chosen == q["answer"] else "Unanswered" if chosen is None else "Review"
            response = chosen if chosen is not None else "No answer selected"
            st.write(f"**{q['question']}** — {status}; your answer: {response}; correct answer: {q['answer']}. {q['explanation']}")
