"""SQLite access, account helpers, and the starter interview question bank."""
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("interview_prep.db")
PASSWORD_HASH_ITERATIONS = 310_000

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
    ("Python", "Why should a mutable list usually not be used as a default argument?", "The same list can be reused across calls", "Lists cannot be function arguments", "It makes the function asynchronous", "Python copies the list on every call", "The same list can be reused across calls", "Default argument objects are created once when the function is defined, so a mutated list can carry state between calls."),
    ("Python", "What is the difference between == and is?", "== compares values; is checks object identity", "== checks identity; is compares values", "They always mean the same thing", "is compares object types only", "== compares values; is checks object identity", "Use == for value equality and is when checking whether two references point to the same object."),
    ("Python", "What does yield do inside a function?", "Produces a value from a generator and pauses it", "Ends the Python program", "Creates a class", "Sorts returned values", "Produces a value from a generator and pauses it", "A generator resumes from where it paused when the next value is requested."),
    ("Python", "What does dictionary.get(key) return when the key is missing and no default is supplied?", "None", "False", "An empty list", "It always raises KeyError", "None", "dict.get returns None for a missing key unless a different default value is provided."),
    ("Python", "Which expression creates a new list containing the squares of numbers in values?", "[x ** 2 for x in values]", "{x ** 2 for x in values}", "(x ** 2 for x in values)", "values.square()", "[x ** 2 for x in values]", "A list comprehension evaluates an expression for each item and collects the results into a list."),
    ("Python", "What is a key benefit of using with open(...) to read a file?", "The file is closed automatically", "The file is always encrypted", "The file is loaded as a database", "The file can never raise an error", "The file is closed automatically", "A context manager closes the file when its block exits, including when an exception occurs."),
    ("SQL", "What does COUNT(*) return in a query?", "The number of rows in the result", "The number of columns in the table", "The largest numeric value", "The number of unique tables", "The number of rows in the result", "COUNT(*) counts result rows, including rows where individual columns contain NULL."),
    ("SQL", "What is GROUP BY commonly used for?", "Grouping rows so aggregate values can be calculated per group", "Sorting every column alphabetically", "Deleting duplicate rows", "Renaming a table", "Grouping rows so aggregate values can be calculated per group", "GROUP BY forms groups of rows, often for aggregates such as COUNT, SUM, or AVG."),
    ("SQL", "Which clause filters groups after GROUP BY has been applied?", "HAVING", "WHERE", "ORDER BY", "FROM", "HAVING", "HAVING filters grouped results; WHERE filters individual rows before grouping."),
    ("SQL", "What does a LEFT JOIN keep when the right table has no matching row?", "The left-table row, with NULL values for right-table columns", "Only matching rows from both tables", "Only unmatched rows from the right table", "It deletes the left-table row", "The left-table row, with NULL values for right-table columns", "A LEFT JOIN preserves every row from the left input and fills unmatched right-side columns with NULL."),
    ("SQL", "How should a query test whether a column has no value (NULL)?", "column_name IS NULL", "column_name = NULL", "column_name == None", "column_name IS EMPTY", "column_name IS NULL", "SQL uses IS NULL and IS NOT NULL because NULL represents an unknown or missing value."),
    ("SQL", "What does COMMIT do in a database transaction?", "Saves the transaction's changes", "Reverses the transaction's changes", "Starts a new database", "Removes a table definition", "Saves the transaction's changes", "COMMIT makes the changes in the current transaction permanent."),
    ("OOP", "What does abstraction help a class do?", "Expose essential behavior while hiding implementation details", "Make every field globally accessible", "Prevent objects from having methods", "Convert methods into database tables", "Expose essential behavior while hiding implementation details", "Abstraction presents a useful interface without requiring callers to know internal details."),
    ("OOP", "What is method overriding?", "A subclass provides its own version of an inherited method", "A method is called twice with the same arguments", "A method is converted into a variable", "A parent class deletes a child class", "A subclass provides its own version of an inherited method", "Overriding lets a subclass specialize behavior defined by its parent class."),
    ("OOP", "Where is a class variable usually shared?", "Across instances of that class", "Only inside one method call", "Only by unrelated classes", "Only while importing the module", "Across instances of that class", "A class variable belongs to the class and is shared unless an instance shadows it."),
    ("OOP", "What is a common use of super() in a subclass?", "Call a method from the parent class", "Create an unrelated global function", "Delete the parent class", "Turn an instance method into a property", "Call a method from the parent class", "super() provides access to the next class in the method resolution order, often for parent initialization."),
    ("Data Structures", "Which structure is commonly used to manage the frontier in breadth-first search?", "Queue", "Stack", "Sorted array", "Hash function", "Queue", "Breadth-first search processes nodes in the order they are discovered, which a queue supports."),
    ("Data Structures", "What is the time complexity of inserting a node at the head of a singly linked list?", "O(1)", "O(log n)", "O(n)", "O(n²)", "O(1)", "Head insertion updates a fixed number of links and does not depend on the list length."),
    ("Data Structures", "In a min-heap, which value is at the root?", "The smallest value", "The largest value", "The most recently inserted value in every case", "The median value in every case", "The smallest value", "A min-heap keeps each parent no greater than its children, so the minimum is at the root."),
    ("Data Structures", "What is the average time complexity of membership lookup in a hash set?", "O(1)", "O(log n)", "O(n log n)", "O(n²)", "O(1)", "Hash sets provide average constant-time membership checks, though worst-case behavior can be slower."),
    ("DBMS", "Why is normalization used in relational database design?", "To reduce unnecessary duplication and update anomalies", "To encrypt every column", "To guarantee queries never need joins", "To make all tables contain the same columns", "To reduce unnecessary duplication and update anomalies", "Normalization organizes related facts to reduce redundancy and inconsistent updates."),
    ("DBMS", "What does atomicity in ACID mean?", "A transaction happens completely or not at all", "Transactions always run in alphabetical order", "Every table has exactly one column", "Data is stored only in memory", "A transaction happens completely or not at all", "Atomicity prevents a transaction from being applied only partially."),
    ("DBMS", "What is a common purpose of a database index?", "Speed up lookups on selected columns", "Replace all table data", "Guarantee that every query is faster", "Automatically encrypt a database", "Speed up lookups on selected columns", "Indexes can speed up searches and joins, while using storage and adding work to writes."),
    ("DBMS", "What is a database transaction?", "A logical unit of work that can be committed or rolled back", "A saved copy of a user interface", "A special type of primary key", "A command that only sorts data", "A logical unit of work that can be committed or rolled back", "Transactions group related database operations so they can succeed or be undone together."),
    ("DBMS", "Which value best follows first normal form (1NF)?", "One atomic value in each table cell", "A comma-separated list of phone numbers in one cell", "A repeating group of columns for each month", "A table with no key", "One atomic value in each table cell", "First normal form requires each field to contain a single value rather than a repeating list."),
    ("Operating Systems", "What is a process?", "A program in execution with its own managed resources", "A variable stored in a spreadsheet", "A file format for source code", "A network cable", "A program in execution with its own managed resources", "The operating system manages a running program as a process with resources such as memory."),
    ("Operating Systems", "How do threads in the same process commonly relate to memory?", "They share the process's memory space", "Each thread always has a separate computer", "Threads cannot access program data", "Every thread has a separate operating system", "They share the process's memory space", "Threads share process resources such as memory, while each thread has its own execution state and stack."),
    ("Operating Systems", "What is a deadlock?", "Tasks wait indefinitely for resources held by one another", "A computer has successfully shut down", "A process finishes before it starts", "A file is compressed", "Tasks wait indefinitely for resources held by one another", "In deadlock, a set of tasks cannot proceed because each waits for a resource held by another."),
    ("Operating Systems", "What does virtual memory paging do?", "Maps fixed-size virtual memory pages to physical frames", "Copies every file to the processor", "Changes a process into a thread", "Deletes unused database rows", "Maps fixed-size virtual memory pages to physical frames", "Paging divides virtual memory into pages and physical memory into frames, managed by the operating system."),
    ("Operating Systems", "What is a context switch?", "The CPU changes from running one task to another", "A program changes its source-code language", "A disk is formatted", "A database commits a transaction", "The CPU changes from running one task to another", "During a context switch, the operating system saves one task's state and restores another's."),
    ("Computer Networks", "What does DNS primarily do?", "Maps domain names to IP addresses", "Encrypts files on a computer", "Assigns table names in SQL", "Measures processor speed", "Maps domain names to IP addresses", "DNS helps clients find the IP address associated with a domain name."),
    ("Computer Networks", "Which statement best describes TCP?", "It provides a reliable, ordered byte stream", "It guarantees the shortest route for every packet", "It is only used for local files", "It has no connection or delivery mechanisms", "It provides a reliable, ordered byte stream", "TCP provides ordered delivery and retransmission for data sent over an IP network."),
    ("Computer Networks", "Which statement about UDP is correct?", "It sends datagrams without guaranteeing delivery or order", "It always retransmits every lost packet", "It is a database query language", "It requires a connection handshake for every message", "It sends datagrams without guaranteeing delivery or order", "UDP is connectionless and has lower protocol overhead, but applications handle reliability if needed."),
    ("Computer Networks", "What does HTTPS add to HTTP?", "TLS protection for the connection", "A relational database", "A faster CPU scheduler", "A guarantee that the website is trustworthy", "TLS protection for the connection", "HTTPS uses TLS to protect data in transit and authenticate the server; it does not guarantee a site is honest."),
    ("Computer Networks", "What does HTTP status code 404 usually mean?", "The requested resource was not found", "The request succeeded", "The server is permanently unavailable", "The user has been authenticated", "The requested resource was not found", "A 404 response indicates that the server could not find the requested resource."),
    ("Behavioral Interview", "What does the STAR method help structure?", "Situation, Task, Action, Result", "Skills, Tools, Application, Review", "Summary, Timeline, Aim, Resume", "Strength, Training, Ability, Role", "Situation, Task, Action, Result", "STAR gives a clear structure for describing the context, responsibility, actions, and outcome of an example."),
    ("Behavioral Interview", "When asked about a challenge, what makes a strong interview response?", "A specific example, your actions, and what you learned", "Blaming another person without context", "Claiming you have never faced a challenge", "Giving unrelated technical definitions", "A specific example, your actions, and what you learned", "A concise real example shows how you respond and reflect on an outcome."),
    ("Behavioral Interview", "If you disagree with a teammate, what is usually the best first step?", "Listen to their reasoning and discuss evidence respectfully", "Ignore them and tell the manager immediately", "Interrupt until they accept your view", "Stop contributing to the project", "Listen to their reasoning and discuss evidence respectfully", "Respectful discussion and shared evidence help resolve disagreements and keep focus on the work."),
    ("Behavioral Interview", "What is a useful way to answer 'Tell me about yourself'?", "Give a brief role-relevant summary of your background and goals", "Recite every personal detail from childhood", "Read your entire resume word for word", "Ask the interviewer to answer first", "Give a brief role-relevant summary of your background and goals", "A focused introduction connects relevant experience, strengths, and interest in the role."),
    ("Behavioral Interview", "What is a good question to ask at the end of an interview?", "What would success in this role look like in the first few months?", "How soon can I avoid doing the main tasks?", "Can I skip the required work?", "Why did you ask me so many questions?", "What would success in this role look like in the first few months?", "This question shows interest in expectations and helps you understand how performance is evaluated."),
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
                email TEXT,
                phone TEXT,
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
            CREATE TABLE IF NOT EXISTS interview_sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                target_role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                answered_count INTEGER NOT NULL,
                transcript_json TEXT NOT NULL,
                feedback TEXT NOT NULL,
                completed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "phone" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email COLLATE NOCASE) WHERE email IS NOT NULL AND email <> ''")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone IS NOT NULL AND phone <> ''")
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
        seed_migration = "question_bank_v2"
        already_seeded = db.execute(
            "SELECT 1 FROM app_migrations WHERE name=?", (seed_migration,)
        ).fetchone()
        if not already_seeded:
            existing = {
                (row["topic"], row["question"])
                for row in db.execute("SELECT topic, question FROM questions")
            }
            missing = [
                question for question in SEED_QUESTIONS
                if (question[0], question[1]) not in existing
            ]
            if missing:
                db.executemany(
                    "INSERT INTO questions(topic,question,option_a,option_b,option_c,option_d,answer,explanation) VALUES(?,?,?,?,?,?,?,?)",
                    missing,
                )
            db.execute("INSERT INTO app_migrations(name) VALUES(?)", (seed_migration,))


def username_exists(username):
    """Return whether a username is already registered."""
    with connect() as db:
        return db.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (username.strip(),)).fetchone() is not None


def email_in_use(email):
    """Return whether an email address is already linked to an account."""
    with connect() as db:
        return db.execute("SELECT 1 FROM users WHERE email=? COLLATE NOCASE", (email.strip(),)).fetchone() is not None


def get_account_by_email(email):
    """Return the account ID for a registered email address, if one exists."""
    normalized_email = email.strip().lower()
    with connect() as db:
        row = db.execute(
            "SELECT id FROM users WHERE email=? COLLATE NOCASE",
            (normalized_email,),
        ).fetchone()
    return {"id": row["id"]} if row else None


def update_user_password(user_id, password):
    """Replace a user's password hash with a freshly salted PBKDF2 hash."""
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    with connect() as db:
        cursor = db.execute(
            "UPDATE users SET salt=?, password_hash=? WHERE id=?",
            (salt, password_hash, user_id),
        )
        return cursor.rowcount == 1


def phone_in_use(phone):
    """Return whether a phone number is already linked to an account."""
    with connect() as db:
        return db.execute("SELECT 1 FROM users WHERE phone=?", (phone.strip(),)).fetchone() is not None


def register_user(username, password, email=None, phone=None):
    """Create an account; the first registered account is the demo admin."""
    username = username.strip()
    email = email.strip().lower() if email else None
    phone = phone.strip() if phone else None
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    try:
        with connect() as db:
            user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if user_count == 0 else "student"
            cursor = db.execute(
                "INSERT INTO users(username,email,phone,salt,password_hash,role) VALUES(?,?,?,?,?,?)",
                (username, email, phone, salt, password_hash, role),
            )
            user_id = cursor.lastrowid
            legacy = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookmarks_legacy'").fetchone()
            if role == "admin":
                if legacy:
                    db.execute("INSERT OR IGNORE INTO bookmarks(user_id,question_id) SELECT ?,question_id FROM bookmarks_legacy", (user_id,))
                    db.execute("DROP TABLE bookmarks_legacy")
                db.execute("UPDATE attempts SET user_id=? WHERE user_id IS NULL", (user_id,))
            return {"id": user_id, "username": username, "email": email, "phone": phone, "role": role}, None
    except sqlite3.IntegrityError:
        if username_exists(username):
            return None, "That username is already taken."
        if email and email_in_use(email):
            return None, "That email address is already linked to an account."
        if phone and phone_in_use(phone):
            return None, "That mobile number is already linked to an account."
        return None, "Could not create the account. Check the details and try again."


def authenticate_user(username, password):
    """Return the account for valid credentials, otherwise None."""
    with connect() as db:
        row = db.execute("SELECT id,username,salt,password_hash,role FROM users WHERE username=? COLLATE NOCASE", (username.strip(),)).fetchone()
    if row is None:
        return None
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), row["salt"], PASSWORD_HASH_ITERATIONS)
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


def save_interview_session(user_id, target_role, interview_type, difficulty,
                           question_count, answered_count, transcript_json,
                           feedback, completed_at):
    """Save one finished AI interview for the signed-in student."""
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO interview_sessions(user_id,target_role,interview_type,difficulty,question_count,answered_count,transcript_json,feedback,completed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (user_id, target_role, interview_type, difficulty, question_count,
             answered_count, transcript_json, feedback, completed_at),
        )
        return cursor.lastrowid


def get_interview_history(user_id, limit=10):
    """Return a student's latest completed AI interview summaries."""
    with connect() as db:
        rows = db.execute(
            "SELECT id,target_role,interview_type,difficulty,question_count,answered_count,feedback,completed_at "
            "FROM interview_sessions WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard(user_id):
    with connect() as db:
        question_count = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        attempt_count, average = db.execute("SELECT COUNT(*), COALESCE(AVG(score),0) FROM attempts WHERE user_id=?", (user_id,)).fetchone()
        bookmark_count = db.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id=?", (user_id,)).fetchone()[0]
        recent = db.execute("SELECT completed_at, topic, score, correct, total FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
        topic_attempts = db.execute(
            "SELECT topic, correct, total, completed_at FROM attempts "
            "WHERE user_id=? AND topic <> 'All topics' ORDER BY id DESC",
            (user_id,),
        ).fetchall()

    topic_summary = {}
    for row in topic_attempts:
        summary = topic_summary.setdefault(row["topic"], {
            "topic": row["topic"], "correct": 0, "total": 0,
            "attempt_count": 0, "last_attempt": row["completed_at"],
        })
        if summary["attempt_count"] >= 3:
            continue
        summary["correct"] += row["correct"]
        summary["total"] += row["total"]
        summary["attempt_count"] += 1
        summary["accuracy"] = round(summary["correct"] * 100 / summary["total"])
    topic_performance = sorted(
        topic_summary.values(),
        key=lambda item: (
            item["correct"] / item["total"],
            -item["attempt_count"],
            item["topic"].casefold(),
        ),
    )
    return {"question_count": question_count, "attempt_count": attempt_count,
            "average_score": average, "bookmark_count": bookmark_count,
            "recent": [tuple(r) for r in reversed(recent)],
            "topic_performance": topic_performance}
