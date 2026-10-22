"""Interview Preparation Portal: Streamlit, SQLite, account login and AI feedback."""
from datetime import datetime
import html
import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import (
    add_attempt, authenticate_user, create_question, delete_question,
    get_bookmarks, get_dashboard, get_questions, init_db, register_user,
    set_bookmark, update_question,
)

st.set_page_config(page_title="Interview Prep Portal", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    :root { --ink:#172443; --muted:#71809b; --primary:#5368e8; --line:#e5eaf3; --surface:#fff; }
    html, body, [class*="css"] { font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    div[data-testid="stAppViewContainer"] { background:#f5f7fc; color:var(--ink); }
    div[data-testid="stHeader"] { background:rgba(245,247,252,.86); }
    .block-container { max-width:1240px; padding-top:2rem; padding-bottom:3rem; }
    section[data-testid="stSidebar"] { background:#101c37; }
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

            with register_tab:
                with st.form("register_form"):
                    new_name = st.text_input("Choose a username", key="register_username")
                    new_password = st.text_input("Choose a password (at least 8 characters)", type="password", key="register_password")
                    confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")
                    register_clicked = st.form_submit_button("Create my account", type="primary", use_container_width=True)
                if register_clicked:
                    if len(new_name.strip()) < 3 or not new_name.strip().replace("_", "").isalnum():
                        st.error("Username must be at least 3 characters and use only letters, numbers or underscores.")
                    elif len(new_password) < 8:
                        st.error("Choose a password with at least 8 characters.")
                    elif new_password != confirm_password:
                        st.error("The passwords do not match.")
                    else:
                        account, error = register_user(new_name, new_password)
                        if error:
                            st.error(error)
                        else:
                            st.session_state.user = account
                            st.success(f"Account created. Your role is {account['role']}.")
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
}
if user["role"] == "admin":
    page_labels["🛠️  Manage Questions"] = "Manage Questions"
selected_page = st.sidebar.radio("YOUR SPACE", list(page_labels))
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
    with st.container(border=True):
        col1, col2 = st.columns([1, 2])
        topic = col1.selectbox("Filter by topic", topics)
        query = col2.text_input("Search the question bank", placeholder="Try a keyword, topic, or concept")
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
            choice = st.radio("Choose an answer", q["options"], key=f"practice_{q['id']}", label_visibility="collapsed")
            left, right = st.columns([1, 3])
            if left.button("Check answer", key=f"check_{q['id']}"):
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
        try:
            ollama_url = st.secrets.get("OLLAMA_BASE_URL", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
            model_name = st.secrets.get("OLLAMA_MODEL", os.environ.get("OLLAMA_MODEL", "gemma3:1b"))
        except Exception:
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            model_name = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
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
                    request_body = json.dumps({
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {"num_predict": 600},
                    }).encode("utf-8")
                    request = Request(
                        f"{ollama_url.rstrip('/')}/api/chat",
                        data=request_body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=180) as response:
                        result = json.loads(response.read().decode("utf-8"))
                    feedback = result.get("message", {}).get("content", "").strip()
                    if feedback:
                        st.markdown(feedback)
                    else:
                        st.error("Ollama returned an empty response. Try asking again.")
                except URLError:
                    st.error("Could not reach Ollama. Make sure the Ollama app is open and the model is installed by running `ollama run gemma3:1b` in PowerShell.")
                except Exception as error:
                    st.error(f"The AI request failed: {error}")

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
    topics = ["All topics"] + sorted({q["topic"] for q in all_questions})
    if "test_active" not in st.session_state:
        st.session_state.test_active = False
    if not st.session_state.test_active:
        topic = st.selectbox("Choose topic", topics)
        count = st.slider("Number of questions", 3, min(10, len(all_questions)), min(5, len(all_questions)))
        minutes = st.slider("Time limit (minutes)", 1, 20, 5)
        if st.button("Start mock test", type="primary"):
            pool = [q for q in all_questions if topic == "All topics" or q["topic"] == topic]
            if len(pool) < count:
                st.warning(f"Only {len(pool)} questions are available for this topic. Reduce the question count.")
            else:
                st.session_state.test_questions = pool[:count]
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
                answer = st.radio("Select one", ["— Select —"] + q["options"], key=f"mock_{q['id']}", label_visibility="collapsed")
                st.session_state.test_answers[q["id"]] = answer
            submitted = st.form_submit_button("Submit test", type="primary")
        if submitted or remaining == 0:
            questions = st.session_state.test_questions
            answers = {str(q["id"]): st.session_state.get(f"mock_{q['id']}", "— Select —") for q in questions}
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
            st.write(f"**{q['question']}** — {'Correct' if chosen == q['answer'] else 'Review'}; answer: {q['answer']}. {q['explanation']}")
