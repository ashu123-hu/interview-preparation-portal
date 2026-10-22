"""Interview Preparation Portal: Streamlit, SQLite, account login and AI feedback."""
from datetime import datetime
import html
import os
import time

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import (
    add_attempt, authenticate_user, create_question, delete_question,
    get_bookmarks, get_dashboard, get_questions, init_db, register_user,
    set_bookmark, update_question,
)

st.set_page_config(page_title="Interview Prep Portal", page_icon="🎯", layout="wide")
init_db()

if "user" not in st.session_state:
    st.title("🎯 Interview Preparation Portal")
    st.caption("Sign in or create an account to continue.")
    login_tab, register_tab = st.tabs(["Login", "Create account"])

    with login_tab:
        with st.form("login_form"):
            login_name = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_clicked = st.form_submit_button("Login", type="primary")
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
            register_clicked = st.form_submit_button("Create account", type="primary")
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
    st.info("The first account created becomes the demo admin. Other accounts are students.")
    st.stop()

user = st.session_state.user
st.sidebar.caption(f"Signed in: **{user['username']}** · {user['role'].title()}")
if st.sidebar.button("Log out"):
    st.session_state.clear()
    st.rerun()

st.title("🎯 Interview Preparation Portal")
st.caption("Practice by topic, get AI feedback, and track your progress.")

pages = ["Dashboard", "Question Bank", "Bookmarks", "Mock Test", "AI Interview Coach"]
if user["role"] == "admin":
    pages.append("Manage Questions")
page = st.sidebar.radio("Go to", pages)

if page == "Dashboard":
    stats = get_dashboard(user["id"])
    a, b, c, d = st.columns(4)
    a.metric("Questions available", stats["question_count"])
    b.metric("Tests completed", stats["attempt_count"])
    c.metric("Average score", f'{stats["average_score"]:.0f}%')
    d.metric("Bookmarked", stats["bookmark_count"])
    st.subheader("Your recent mock tests")
    recent = stats["recent"]
    if recent:
        df = pd.DataFrame(recent, columns=["Date", "Topic", "Score (%)", "Correct", "Total"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.subheader("Scores over time")
        st.line_chart(df.set_index("Date")["Score (%)"])
    else:
        st.info("Complete a mock test to start building your progress history.")
    st.subheader("Study plan")
    st.write("Choose one topic, practise a short set of questions, review explanations, then use a timed mock test to check recall.")

elif page == "Question Bank":
    st.subheader("Topic-wise question bank")
    all_questions = get_questions()
    topics = ["All topics"] + sorted({q["topic"] for q in all_questions})
    col1, col2 = st.columns([1, 2])
    topic = col1.selectbox("Topic", topics)
    query = col2.text_input("Search questions", placeholder="Search question text or topic")
    selected = [q for q in all_questions if (topic == "All topics" or q["topic"] == topic)
                and query.lower() in (q["question"] + q["topic"]).lower()]
    st.caption(f"{len(selected)} question(s)")
    bookmarks = get_bookmarks(user["id"])
    for q in selected:
        with st.container(border=True):
            st.markdown(f"**{q['topic']}** · {html.escape(q['question'])}")
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
    st.subheader("Saved questions")
    saved = [q for q in get_questions() if q["id"] in get_bookmarks(user["id"])]
    if not saved:
        st.info("No bookmarks yet. Save questions from the Question Bank.")
    for q in saved:
        with st.container(border=True):
            st.markdown(f"**{q['topic']}** · {html.escape(q['question'])}")
            st.write(f"Answer: **{q['answer']}** — {q['explanation']}")
            if st.button("Remove bookmark", key=f"remove_{q['id']}"):
                set_bookmark(q["id"], False, user["id"])
                st.rerun()

elif page == "AI Interview Coach":
    st.subheader("AI Interview Coach")
    st.write("Write an interview question and your answer. The AI will review the answer and suggest improvements.")
    st.caption("Avoid entering private or personally identifying information. Your answer is sent to the configured AI API for feedback.")
    with st.form("ai_feedback_form"):
        target_role = st.text_input("Target role", placeholder="e.g. Python developer")
        topic = st.text_input("Topic", placeholder="e.g. Python, SQL, communication")
        interview_question = st.text_area("Interview question")
        candidate_answer = st.text_area("Your answer", height=180)
        ask_ai = st.form_submit_button("Get AI feedback", type="primary")
    if ask_ai:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY", "")
            model_name = st.secrets.get("OPENAI_MODEL", "gpt-6-astra")
        except Exception:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            model_name = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
        if not api_key:
            st.error("AI is not configured yet. Add OPENAI_API_KEY to your local Streamlit secrets or Community Cloud app settings.")
        elif not interview_question.strip() or not candidate_answer.strip():
            st.warning("Enter both the interview question and your answer.")
        else:
            from openai import OpenAI

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
                    client = OpenAI(api_key=api_key)
                    response = client.responses.create(
                        model=model_name,
                        instructions=instructions,
                        input=prompt,
                        max_output_tokens=600,
                    )
                    st.markdown(response.output_text)
                except Exception:
                    st.error("The AI request failed. Check the API key, model setting, internet connection and API access, then try again.")

elif page == "Manage Questions":
    if user["role"] != "admin":
        st.error("Only the demo admin can manage the shared question bank.")
        st.stop()
    st.subheader("Manage Questions — CRUD")
    st.caption("Add, view, edit or delete MCQs in the SQLite question bank.")
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
    st.subheader("Timed mock test")
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
