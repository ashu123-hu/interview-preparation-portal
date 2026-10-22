"""SQLite access, account helpers, and the starter interview question bank."""
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("interview_prep.db")

SEED_QUESTIONS = [
    ("Python", "What is the main purpose of a Python dictionary?", "Store key-value pairs", "Store only ordered numbers", "Define a function", "Create a loop", "Store key-value pairs", "A dictionary maps unique keys to values for efficient lookup."),
    ("Python", "Which keyword is used to define a function?", "func", "def", "function", "lambda", "def", "The def statement creates a named function; lambda creates a small anonymous function."),
    ("Python", "What does list.append(x) do?", "Adds x to the end of the list", "Sorts the list", "Removes x", "Returns a copy", "Adds x to the end of the list", "append mutates the list by adding one item at its end."),
    ("Python", "Which structure handles errors in Python?", "if/else", "try/except", "for/in", "with/as", "try/except", "try/except catches selected exceptions so a program can handle failures."),
    ("Python", "What is a tuple?", "An immutable sequence", "A key-value map", "A file object", "A mutable set", "An immutable sequence", "Tuples are ordered sequences whose elements cannot be reassigned."),
    ("SQL", "Which SQL command retrieves rows from a table?", "SELECT", "INSERT", "UPDATE", "ALTER", "SELECT", "SELECT reads data from one or more tables."),
    ("SQL", "What does a primary key guarantee?", "Unique identification of each row", "Rows are alphabetically sorted", "Every field is encrypted", "The table has one column", "Unique identification of each row", "A primary key is unique and non-null for each row."),
    ("SQL", "Which clause filters rows before grouping?", "ORDER BY", "WHERE", "HAVING", "LIMIT", "WHERE", "WHERE filters input rows; HAVING filters groups after aggregation."),
    ("SQL", "What is the purpose of a foreign key?", "Link related tables", "Encrypt a column", "Sort query output", "Rename a table", "Link related tables", "A foreign key references a key in another table to preserve relationships."),
    ("SQL", "Which operation combines rows from related tables?", "JOIN", "DROP", "TRUNCATE", "COMMIT", "JOIN", "JOIN combines rows according to a relationship between tables."),
    ("OOP", "What is encapsulation?", "Bundling data and methods with controlled access", "Copying an object", "Sorting methods", "Running code in parallel", "Bundling data and methods with controlled access", "Encapsulation keeps state and behavior together and limits unintended access."),
    ("OOP", "Which concept lets a subclass reuse a parent class's behavior?", "Inheritance", "Iteration", "Compilation", "Serialization", "Inheritance", "Inheritance allows a class to extend or specialize another class."),
    ("OOP", "What is polymorphism?", "One interface with different implementations", "One object stored twice", "A class with no methods", "A private variable", "One interface with different implementations", "Polymorphism lets the same operation behave differently for different types."),
    ("OOP", "In Python, what does __init__ typically do?", "Initializes a new instance", "Deletes an instance", "Imports a module", "Catches exceptions", "Initializes a new instance", "__init__ sets up instance state when an object is created."),
    ("OOP", "Why use composition?", "Build behavior by combining collaborating objects", "Avoid creating objects", "Convert code to SQL", "Make every method static", "Build behavior by combining collaborating objects", "Composition gives an object other objects to delegate work to."),
    ("Data Structures", "Which structure follows FIFO order?", "Queue", "Stack", "Tree", "Set", "Queue", "A queue removes items in the order they were added: first in, first out."),
    ("Data Structures", "Which structure follows LIFO order?", "Stack", "Queue", "Graph", "Hash table", "Stack", "A stack removes the most recently added item first."),
    ("Data Structures", "Average lookup in a well-sized hash table is typically?", "O(1)", "O(n)", "O(n log n)", "O(n²)", "O(1)", "Hashing provides constant average-time lookup, though collisions can worsen it."),
    ("Data Structures", "Which traversal visits a binary search tree in sorted order?", "In-order", "Pre-order", "Post-order", "Level-order", "In-order", "For a binary search tree, in-order traversal visits left, node, then right."),
    ("Data Structures", "What is the time complexity of binary search on sorted data?", "O(log n)", "O(n)", "O(n²)", "O(1) always", "O(log n)", "Each comparison removes about half of the remaining search range."),
]


def connect():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','student')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY, topic TEXT NOT NULL, question TEXT NOT NULL,
                option_a TEXT NOT NULL, option_b TEXT NOT NULL,
                option_c TEXT NOT NULL, option_d TEXT NOT NULL,
                answer TEXT NOT NULL, explanation TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                PRIMARY KEY(user_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, topic TEXT NOT NULL, score INTEGER NOT NULL,
                correct INTEGER NOT NULL, total INTEGER NOT NULL, completed_at TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        bookmark_columns = {row[1] for row in db.execute("PRAGMA table_info(bookmarks)")}
        if "user_id" not in bookmark_columns:
            db.execute("ALTER TABLE bookmarks RENAME TO bookmarks_legacy")
            db.execute("""CREATE TABLE bookmarks (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                PRIMARY KEY(user_id, question_id)
            )""")
        attempt_columns = {row[1] for row in db.execute("PRAGMA table_info(attempts)")}
        if "user_id" not in attempt_columns:
            db.execute("ALTER TABLE attempts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            db.executemany("INSERT INTO questions(topic,question,option_a,option_b,option_c,option_d,answer,explanation) VALUES(?,?,?,?,?,?,?,?)", SEED_QUESTIONS)


def register_user(username, password):
    """Create an account; the first registered account is the demo admin."""
    username = username.strip()
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    try:
        with connect() as db:
            user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if user_count == 0 else "student"
            cursor = db.execute(
                "INSERT INTO users(username,salt,password_hash,role) VALUES(?,?,?,?)",
                (username, salt, password_hash, role),
            )
            user_id = cursor.lastrowid
            legacy = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookmarks_legacy'").fetchone()
            if role == "admin":
                if legacy:
                    db.execute("INSERT OR IGNORE INTO bookmarks(user_id,question_id) SELECT ?,question_id FROM bookmarks_legacy", (user_id,))
                    db.execute("DROP TABLE bookmarks_legacy")
                db.execute("UPDATE attempts SET user_id=? WHERE user_id IS NULL", (user_id,))
            return {"id": user_id, "username": username, "role": role}, None
    except sqlite3.IntegrityError:
        return None, "That username is already taken."


def authenticate_user(username, password):
    """Return the account for valid credentials, otherwise None."""
    with connect() as db:
        row = db.execute("SELECT id,username,salt,password_hash,role FROM users WHERE username=? COLLATE NOCASE", (username.strip(),)).fetchone()
    if row is None:
        return None
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), row["salt"], 310_000)
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def get_questions():
    with connect() as db:
        rows = db.execute("SELECT * FROM questions ORDER BY topic, id").fetchall()
    return [{"id": r["id"], "topic": r["topic"], "question": r["question"],
             "options": [r["option_a"], r["option_b"], r["option_c"], r["option_d"]],
             "answer": r["answer"], "explanation": r["explanation"]} for r in rows]


def create_question(topic, question, options, answer, explanation):
    """Create one MCQ and return its new database ID."""
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO questions(topic,question,option_a,option_b,option_c,option_d,answer,explanation) VALUES(?,?,?,?,?,?,?,?)",
            (topic.strip(), question.strip(), *[option.strip() for option in options], answer.strip(), explanation.strip()),
        )
        return cursor.lastrowid


def update_question(question_id, topic, question, options, answer, explanation):
    """Update an existing MCQ."""
    with connect() as db:
        db.execute(
            "UPDATE questions SET topic=?, question=?, option_a=?, option_b=?, option_c=?, option_d=?, answer=?, explanation=? WHERE id=?",
            (topic.strip(), question.strip(), *[option.strip() for option in options], answer.strip(), explanation.strip(), question_id),
        )


def delete_question(question_id):
    """Delete one MCQ; linked bookmarks are removed by the foreign key."""
    with connect() as db:
        db.execute("DELETE FROM questions WHERE id=?", (question_id,))


def get_bookmarks(user_id):
    with connect() as db:
        return {r[0] for r in db.execute("SELECT question_id FROM bookmarks WHERE user_id=?", (user_id,))}


def set_bookmark(question_id, saved, user_id):
    with connect() as db:
        if saved:
            db.execute("INSERT OR IGNORE INTO bookmarks(user_id,question_id) VALUES(?,?)", (user_id, question_id))
        else:
            db.execute("DELETE FROM bookmarks WHERE user_id=? AND question_id=?", (user_id, question_id))


def add_attempt(topic, score, correct, total, completed_at, user_id):
    with connect() as db:
        db.execute("INSERT INTO attempts(topic,score,correct,total,completed_at,user_id) VALUES(?,?,?,?,?,?)", (topic, score, correct, total, completed_at, user_id))


def get_dashboard(user_id):
    with connect() as db:
        question_count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        attempt_count, average = db.execute("SELECT COUNT(*), COALESCE(AVG(score),0) FROM attempts WHERE user_id=?", (user_id,)).fetchone()
        bookmark_count = db.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id=?", (user_id,)).fetchone()[0]
        recent = db.execute("SELECT completed_at, topic, score, correct, total FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
    return {"question_count": question_count, "attempt_count": attempt_count,
            "average_score": average, "bookmark_count": bookmark_count,
            "recent": [tuple(r) for r in reversed(recent)]}
