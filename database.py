"""SQLite access and starter interview question bank."""
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
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY, topic TEXT NOT NULL, question TEXT NOT NULL,
                option_a TEXT NOT NULL, option_b TEXT NOT NULL,
                option_c TEXT NOT NULL, option_d TEXT NOT NULL,
                answer TEXT NOT NULL, explanation TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, topic TEXT NOT NULL, score INTEGER NOT NULL,
                correct INTEGER NOT NULL, total INTEGER NOT NULL, completed_at TEXT NOT NULL
            );
        """)
        count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            db.executemany("INSERT INTO questions(topic,question,option_a,option_b,option_c,option_d,answer,explanation) VALUES(?,?,?,?,?,?,?,?)", SEED_QUESTIONS)


def get_questions():
    with connect() as db:
        rows = db.execute("SELECT * FROM questions ORDER BY topic, id").fetchall()
    return [{"id": r["id"], "topic": r["topic"], "question": r["question"],
             "options": [r["option_a"], r["option_b"], r["option_c"], r["option_d"]],
             "answer": r["answer"], "explanation": r["explanation"]} for r in rows]


def get_bookmarks():
    with connect() as db:
        return {r[0] for r in db.execute("SELECT question_id FROM bookmarks")}


def set_bookmark(question_id, saved):
    with connect() as db:
        if saved:
            db.execute("INSERT OR IGNORE INTO bookmarks(question_id) VALUES(?)", (question_id,))
        else:
            db.execute("DELETE FROM bookmarks WHERE question_id=?", (question_id,))


def add_attempt(topic, score, correct, total, completed_at):
    with connect() as db:
        db.execute("INSERT INTO attempts(topic,score,correct,total,completed_at) VALUES(?,?,?,?,?)", (topic, score, correct, total, completed_at))


def get_dashboard():
    with connect() as db:
        question_count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        attempt_count, average = db.execute("SELECT COUNT(*), COALESCE(AVG(score),0) FROM attempts").fetchone()
        bookmark_count = db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        recent = db.execute("SELECT completed_at, topic, score, correct, total FROM attempts ORDER BY id DESC LIMIT 20").fetchall()
    return {"question_count": question_count, "attempt_count": attempt_count,
            "average_score": average, "bookmark_count": bookmark_count,
            "recent": [tuple(r) for r in reversed(recent)]}
