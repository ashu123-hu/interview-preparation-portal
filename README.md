# Interview Preparation Portal

A college project built with Python, Streamlit and SQLite. It supports account login, admin question CRUD, topic-based MCQ practice, per-user bookmarks and score history, timed mock tests, an AI answer coach and a dashboard.

## Feasible one-to-two week plan

| Days | Work | Checkpoint |
|---|---|---|
| 1 | Confirm features, sketch page flow and database tables | Scope and schema agreed |
| 2–3 | Create SQLite tables and seed an initial question bank | Questions load from the database |
| 4–5 | Build question CRUD, topic practice, search, feedback and bookmarks | Admin can manage questions |
| 6–7 | Add timed mock tests, login and per-user history | Accounts keep separate progress |
| 8–9 | Add AI answer feedback and dashboard | AI can review a sample response |
| 10–11 | Check setup on a clean environment; fix defects | Reliable local run |
| 12–14 | Prepare slides, rehearse the demo and viva | Presentation ready |

Keep the first version focused on a small question bank and a supervised demo. The login and admin controls are suitable for a college prototype, not production authentication.

## Setup

Use Python 3.10 or newer. From this folder:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

For free local AI feedback, install [Ollama for Windows](https://ollama.com/download/windows), then open PowerShell and run:

```powershell
ollama run gemma3:1b
```

The model downloads the first time. Keep the Ollama app running while you use the AI Interview Coach. The portal connects to Ollama at `http://localhost:11434` and uses `gemma3:1b` by default, so no API key or `.streamlit/secrets.toml` is needed. To select another installed Ollama model or server URL, set `OLLAMA_MODEL` or `OLLAMA_BASE_URL` in Streamlit secrets or environment variables. This local setup works when the portal and Ollama run on the same computer; a cloud-hosted portal cannot reach Ollama on your personal PC.

Open the local URL printed by Streamlit, usually `http://localhost:8501`. The SQLite file `interview_prep.db` is created next to `app.py` on first launch and is not required in source control; the starter questions are inserted automatically when the database is empty.

To reset the demo data, stop the app and delete `interview_prep.db`; it will be recreated on the next launch.

## Demo walkthrough

1. Create the first account; it becomes the demo admin. Subsequent accounts are students.
2. Show the dashboard, then open Question Bank to search and practise a question.
3. Sign in as admin and demonstrate Create, Read, Update and Delete in Manage Questions.
4. Bookmark a question, then show it on the Bookmarks page.
5. Start a timed mock test and show that the score is saved to the signed-in account.
6. Open AI Interview Coach, enter a sample answer and show the feedback.

## Design notes

- `app.py` contains the Streamlit interface, login flow and page routing.
- `database.py` initializes SQLite, hashes passwords, and provides account and data functions.
- The database has `users`, `questions`, `bookmarks` and `attempts` tables. Bookmarks and attempts are associated with a user; bookmarks also reference questions through a foreign key.
- The Manage Questions page implements question CRUD: add MCQs, list them, edit their fields, and delete them. Deleting a question also removes linked bookmarks through the foreign-key cascade.
- The first registered account receives the admin role; later accounts are students. Passwords are stored as salted PBKDF2 hashes, not plain text.
- The AI Interview Coach sends the entered question and answer to the local Ollama server and displays coaching feedback. No OpenAI API key is required. Avoid entering private personal information in the coach.
- Correct answers are compared in Python. The attempt score is `correct / total × 100`, rounded to a whole percentage.
- The timed test keeps its deadline in Streamlit session state and refreshes once per second. A refresh or browser session reset ends an in-progress test; completed attempts are saved in SQLite.
- The demo starts with 20 questions across Python, SQL, OOP and Data Structures. It is a learning prototype, not an authoritative interview syllabus.
- This is a student demo, not production authentication. The first-account admin rule is intended for a supervised project demo. On Community Cloud, SQLite files are not guaranteed to persist after app restarts, so saved accounts, bookmarks and attempts may reset.

## Troubleshooting

- If Streamlit is not found, run `.venv\Scripts\python.exe -m pip install -r requirements.txt` again.
- If the port is busy, run `streamlit run app.py --server.port 8502`.
- If the database schema is changed during development, stop the app and remove the local demo database to let initialization create it again.
