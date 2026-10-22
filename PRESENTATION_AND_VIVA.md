# Presentation and viva preparation

## Suggested 5-minute presentation

### Slide 1 — Interview Preparation Portal
**Say:** “This project is a web portal that helps students practise interview questions, take timed mock tests, get AI feedback and review their progress.”

### Slide 2 — Problem and objective
- Students need a focused way to practise by topic.
- Repeated practice is more useful when learners can save questions and see results.
- Objective: bring practice, mock tests and progress history into one simple app.

**Say:** “The goal was to build a practical study tool with a small, achievable feature set for a one-to-two week project.”

### Slide 3 — Features and user flow
- Search or filter 60 MCQs across Python, SQL, OOP, Data Structures, DBMS, Operating Systems, Computer Networks and Behavioral Interview.
- Verify an email address at signup, then log in; the first account is admin and later accounts are students.
- Create, view, edit and delete MCQs from Manage Questions.
- Check answers and read short explanations.
- Bookmark questions for revision.
- Take a timed test; receive score and review.
- Ask the AI coach for feedback on a written answer.
- Track past attempts on the dashboard.

**Say:** “The first account is an admin that manages questions with CRUD. Students can practise, take tests and get AI feedback on a written answer.”

### Slide 4 — Technology and architecture
- Python runs the application logic.
- Streamlit provides the browser interface.
- SQLite stores user accounts, the question bank, bookmarks and test attempts.
- Brevo's transactional email API delivers the signup code; Python checks it before account creation.
- A locally running Ollama model provides AI answer feedback without a paid API key.
- Pandas prepares the small attempt history for display.

**Say:** “The browser interface calls database helper functions. SQLite keeps the demo easy to run without a separate database server.”

### Slide 5 — Database design
- `questions`: topic, question, four options, correct answer and explanation.
- `bookmarks`: saved question IDs, linked to questions.
- `attempts`: topic, score, correct count, total and completion time.
- `app_migrations`: records one-time question-bank updates for existing databases.
- `users`: username, verified email address, salted password hash, role and account creation time.

**Say:** “The email address is saved after signup verification. User IDs keep bookmarks and scores separate, and the admin page uses CRUD for question records.”

### Slide 6 — AI Interview Coach
- Sends a written answer and interview question to a language model.
- Returns strengths, improvements, a sample answer and a follow-up question.
- Uses the `gemma3:1b` model through Ollama on the same computer.
- No OpenAI API key or usage payment is needed for the local demo.

**Say:** “I connected the coach to a small language model running locally with Ollama. That avoids API charges for the classroom demo.”

### Slide 7 — Mock-test scoring and timer
- A deadline is stored in the active Streamlit session.
- The interface refreshes each second to show remaining time.
- Score = correct answers ÷ total questions × 100.
- Results and explanations appear after submission or timeout.

**Say:** “The deadline is session data, while completed scores are persistent database data. The timed session itself is intentionally simple.”

### Slide 8 — Demonstration and progress
- Add or edit a sample MCQ in Manage Questions.
- Show the question in the Question Bank, then delete the sample.
- Filter and search the question bank.
- Save a question and find it in Bookmarks.
- Finish a short mock test.
- Return to the dashboard to view the saved result.

**Say:** “This walkthrough follows one learner from practice to revision to a measured mock test.”

### Slide 9 — Limitations and next steps
- Demo authentication; signup verification needs a configured email provider, and there is no password reset or production-grade admin setup.
- SQLite data on cloud hosting may reset after an app restart.
- The 60-question starter bank needs further expert review and role-specific expansion.
- Active test state is not restored if the session is refreshed; local AI requires Ollama to be running on the same computer.
- Next: durable cloud storage, password recovery and more curated questions.

**Say:** “The next improvements would focus on content quality and multi-user support after validating the core learning flow.”

## Viva questions and short answers

1. **What problem does the portal solve?** It organizes interview practice, timed assessment, AI coaching and progress review.
2. **What does CRUD mean, and where is it used?** Create, Read, Update and Delete. The admin Manage Questions page performs all four on SQLite question records.
3. **How does signup email verification work?** Python generates a six-digit code, Brevo sends it to the entered address and the app checks it before creating the account.
4. **What is the code's expiry and attempt limit?** It expires after 10 minutes and allows five attempts.
5. **Does email verification prove someone's identity?** No. It only confirms that they can access the email inbox.
6. **How does login work?** The account is looked up by username and the entered password is hashed with the saved salt and compared with the stored hash.
7. **Are passwords stored in plain text?** No. A salted PBKDF2 hash is stored instead of the original password.
8. **Why is the first account an admin?** It lets the project owner manage the question bank; later registered accounts receive the student role.
9. **How does the AI feature work?** It sends the interview question and candidate answer to the local Ollama server and displays generated coaching feedback.
10. **Does the AI feature need a paid key?** No. The demo uses a local Ollama model, so there is no OpenAI API key or API usage charge.
11. **Why did you choose Streamlit?** It lets a Python student build an interactive browser interface without a separate front-end stack.
12. **Why SQLite?** It is file-based, requires no database server and suits a local prototype.
13. **What are the main database tables?** `users`, `questions`, `bookmarks` and `attempts`.
14. **How are user records separated?** Each bookmark and test attempt stores a user ID, and queries filter by that ID.
15. **How do you calculate the score?** Correct answers divided by total questions, multiplied by 100 and rounded.
16. **How does the timer work?** The app stores an end timestamp in session state and recalculates remaining seconds on refresh.
17. **What are the limitations?** Signup needs Brevo setup and internet access; the free plan has a daily sending limit, the app is a demo, and cloud SQLite data may reset.
18. **What would you improve next?** Add password reset, stronger admin provisioning, durable cloud storage and more curated interview questions.
19. **Why are answer choices unselected when a question opens?** Learners should choose their own answer; the stored answer key is only used after submission to check the response and calculate the score.
20. **How does an existing database get the new questions?** A one-time versioned migration inserts missing starter questions while preserving existing accounts, bookmarks and attempts.

## Likely demo questions

- **Can the presenter add questions in the interface?** Yes. The admin account can create, edit and delete questions; the starter bank is seeded by `database.py`.
- **Does the portal need internet access?** No, after dependencies are installed; it runs locally.
- **Will scores survive a restart?** Yes. Completed attempts and bookmarks are stored in SQLite.
- **Will an unfinished test survive a restart?** No. Its active deadline and answers are held in Streamlit session state.
- **What does Brevo do here?** It delivers transactional signup emails. The Brevo API key lives in local Streamlit secrets and should not be committed to GitHub.
- **Can the AI coach run without a key?** Yes. Install Ollama, download the configured model once, and keep Ollama running on the same computer as the portal.
