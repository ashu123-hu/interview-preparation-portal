"""Interview Preparation Portal: a single-user Streamlit learning demo."""
from datetime import datetime, timedelta
import html
import time

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import (
    add_attempt, get_bookmarks, get_dashboard, get_questions, init_db,
    set_bookmark,
)

st.set_page_config(page_title="Interview Prep Portal", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 Interview Preparation Portal")
st.caption("Practice by topic, save useful questions, and track your progress.")

page = st.sidebar.radio("Go to", ["Dashboard", "Question Bank", "Bookmarks", "Mock Test"])

if page == "Dashboard":
    stats = get_dashboard()
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
    bookmarks = get_bookmarks()
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
                set_bookmark(q["id"], not is_saved)
                st.rerun()

elif page == "Bookmarks":
    st.subheader("Saved questions")
    saved = [q for q in get_questions() if q["id"] in get_bookmarks()]
    if not saved:
        st.info("No bookmarks yet. Save questions from the Question Bank.")
    for q in saved:
        with st.container(border=True):
            st.markdown(f"**{q['topic']}** · {html.escape(q['question'])}")
            st.write(f"Answer: **{q['answer']}** — {q['explanation']}")
            if st.button("Remove bookmark", key=f"remove_{q['id']}"):
                set_bookmark(q["id"], False)
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
            add_attempt(st.session_state.test_topic, score, correct, len(questions), datetime.now().isoformat(timespec="seconds"))
            st.session_state.last_result = (score, correct, len(questions), questions, answers)
            st.session_state.test_active = False
            st.rerun()
    if "last_result" in st.session_state and not st.session_state.test_active:
        score, correct, total, questions, answers = st.session_state.last_result
        st.success(f"Score: {score}% ({correct}/{total})")
        for q in questions:
            chosen = answers[str(q["id"])]
            st.write(f"**{q['question']}** — {'Correct' if chosen == q['answer'] else 'Review'}; answer: {q['answer']}. {q['explanation']}")
