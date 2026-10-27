
from datetime import date
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "ai-study-assistant-secret"


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT NOT NULL,
            due_date TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending'
        )
    """)

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'Medium'")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                score INTEGER,
                total INTEGER
            )
        """)

    conn.commit()
    conn.close()


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # Hash password before saving
        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:

            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                message="Email already registered!"
            )

    return render_template("register.html")


# ---------------- LOGIN ----------------

# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        # Find user using email only
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user:

            stored_password = user["password"]

            # Check hashed password
            if check_password_hash(stored_password, password):

                session["user_id"] = user["id"]
                session["name"] = user["name"]

                conn.close()

                return redirect("/dashboard")

        conn.close()

        return render_template(
            "login.html",
            message="Invalid email or password!"
        )

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    total_tasks = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0]

    completed_tasks = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'Completed'",
        (session["user_id"],)
    ).fetchone()[0]

    pending_tasks = total_tasks - completed_tasks

    last_quiz = conn.execute(
        """
        SELECT score, total
        FROM quiz_scores
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (session["user_id"],)
    ).fetchone()


        # ---------------- QUIZ HISTORY ----------------

    quiz_history = conn.execute(
        """
        SELECT score, total
        FROM quiz_scores
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    total_quizzes = len(quiz_history)

    best_score = 0

    for quiz in quiz_history:

        if quiz["score"] > best_score:
            best_score = quiz["score"]

    quiz_percentage = 0

    if last_quiz:

        quiz_percentage = round(
            (last_quiz["score"] / last_quiz["total"]) * 100
        )




    if total_tasks > 0:
        progress = round((completed_tasks / total_tasks) * 100)
    else:
        progress = 0

    conn.close()

    return render_template(
        "dashboard.html",
        name=session["name"],
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        progress=progress,
        last_quiz=last_quiz,
        quiz_history=quiz_history,
        total_quizzes=total_quizzes,
        best_score=best_score,
        quiz_percentage=quiz_percentage
    )

   


# ---------------- STUDY PLANNER ----------------

# ---------------- STUDY PLANNER ----------------

@app.route("/planner", methods=["GET", "POST"])
def planner():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        task = request.form["task"]
        due_date = request.form["due_date"]
        priority = request.form["priority"]

        conn.execute(
            """
            INSERT INTO tasks
            (user_id, task, due_date, priority)
            VALUES (?, ?, ?, ?)
            """,
            (
                session["user_id"],
                task,
                due_date,
                priority
            )
        )

        conn.commit()

    tasks = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY
            CASE
                WHEN status = 'Completed' THEN 1
                ELSE 0
            END,
            due_date ASC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    today = date.today().isoformat()
    return render_template(
        "planner.html",
        tasks=tasks,
        today= today
    )

# ---------------- COMPLETE TASK ----------------

@app.route("/complete/<int:task_id>")
def complete_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute(
        "UPDATE tasks SET status = 'Completed' WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/planner")


# ---------------- DELETE TASK ----------------

@app.route("/delete/<int:task_id>")
def delete_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/planner")

# ---------------- EDIT TASK ----------------

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        task = request.form["task"]
        due_date = request.form["due_date"]
        priority = request.form["priority"]

        conn.execute(
            """
            UPDATE tasks
            SET task = ?, due_date = ?, priority = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                task,
                due_date,
                priority,
                task_id,
                session["user_id"]
            )
        )

        conn.commit()
        conn.close()

        return redirect("/planner")

    selected_task = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, session["user_id"])
    ).fetchone()

    conn.close()

    if not selected_task:
        return redirect("/planner")

    return render_template(
        "edit_task.html",
        task=selected_task
    )

# ---------------- QUIZ ----------------

# ---------------- QUIZ ----------------

@app.route("/quiz", methods=["GET", "POST"])
def quiz():

    score = None
    percentage = None

    if request.method == "POST":

        score = 0

        answers = {
            "q1": "Python",
            "q2": "HTML",
            "q3": "SQLite",
            "q4": "CSS",
            "q5": "Flask"
        }

        for question, correct_answer in answers.items():

            if request.form.get(question) == correct_answer:
                score += 1

        percentage = round((score / 5) * 100)

        # Save quiz score
        if "user_id" in session:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO quiz_scores
                (user_id, score, total)
                VALUES (?, ?, ?)
                """,
                (session["user_id"], score, 5)
            )

            conn.commit()
            conn.close()

    return render_template(
        "quiz.html",
        score=score,
        percentage=percentage
    )

# ---------------- AI ASSISTANT ----------------

@app.route("/ai", methods=["GET", "POST"])
def ai():

    question = ""
    answer = ""

    if request.method == "POST":

        question = request.form["question"]

        question_lower = question.lower().strip()


        # -------- PYTHON --------

        if "what is python" in question_lower:

            answer = "Python is a high-level, beginner-friendly programming language used for web development, AI, data science and automation."

        elif "python features" in question_lower:

            answer = "Main features of Python are simple syntax, easy to learn, interpreted language, object-oriented programming, portability and a large number of libraries."

        elif "variable" in question_lower and "python" in question_lower:

            answer = "A variable in Python is a name used to store a value. Example: name = 'Abhishek' and age = 22."

        elif "list" in question_lower and "python" in question_lower:

            answer = "A list in Python is an ordered and changeable collection of elements. Example: fruits = ['Apple', 'Mango', 'Banana']."

        elif "tuple" in question_lower and "python" in question_lower:

            answer = "A tuple is an ordered collection in Python that cannot be changed after creation. Example: numbers = (10, 20, 30)."

        elif "dictionary" in question_lower and "python" in question_lower:

            answer = "A dictionary stores data in key-value pairs. Example: student = {'name': 'Abhishek', 'age': 22}."

        elif "loop" in question_lower and "python" in question_lower:

            answer = "A loop is used to repeat a block of code. Python mainly provides for loops and while loops."

        elif "function" in question_lower and "python" in question_lower:

            answer = "A function is a reusable block of code. In Python, a function is created using the def keyword."

        elif "if else" in question_lower and "python" in question_lower:

            answer = "if-else statements are used for decision making in Python. The if block runs when the condition is true, otherwise the else block runs."


        # -------- HTML --------

        elif "what is html" in question_lower:

            answer = "HTML stands for HyperText Markup Language. It is used to create the structure of web pages."

        elif "html tags" in question_lower:

            answer = "HTML tags are keywords enclosed in angle brackets. Examples are <html>, <head>, <body>, <h1> and <p>."

        elif "heading" in question_lower and "html" in question_lower:

            answer = "HTML headings are created using h1 to h6 tags. h1 is the largest heading and h6 is the smallest."

        elif "paragraph" in question_lower and "html" in question_lower:

            answer = "The HTML <p> tag is used to create a paragraph."

        elif "link" in question_lower and "html" in question_lower:

            answer = "The HTML <a> tag is used to create a hyperlink. Example: <a href='https://example.com'>Visit</a>."

        elif "image" in question_lower and "html" in question_lower:

            answer = "The HTML <img> tag is used to display an image. Example: <img src='image.jpg' alt='Image'>."

        elif "form" in question_lower and "html" in question_lower:

            answer = "The HTML <form> tag is used to create forms for collecting user input such as name, email and password."

        elif "div" in question_lower and "html" in question_lower:

            answer = "The HTML <div> tag is a container used to group and organize HTML elements."


        # -------- CSS --------

        elif "what is css" in question_lower:

            answer = "CSS stands for Cascading Style Sheets. It is used to style and design HTML web pages."

        elif "css" in question_lower and "color" in question_lower:

            answer = "CSS can change text color using the color property. Example: color: blue;"

        elif "css" in question_lower and "background" in question_lower:

            answer = "The CSS background-color property is used to change the background color of an element."


        # -------- FLASK --------

        elif "what is flask" in question_lower:

            answer = "Flask is a lightweight Python web framework used to create web applications."

        elif "flask route" in question_lower:

            answer = "A Flask route connects a URL to a Python function. Example: @app.route('/home')"


        # -------- DATABASE --------

        elif "what is database" in question_lower:

            answer = "A database is used to store, organize and manage data."

        elif "sqlite" in question_lower:

            answer = "SQLite is a lightweight, serverless database that stores data in a single database file. We are using SQLite in this project."


        # -------- DEFAULT --------

        else:

            answer = "I can answer common questions about Python, HTML, CSS, Flask and Database. Try asking: What is Python? What is a list in Python? What is HTML? What is CSS? What is Flask?"


    return render_template(
        "ai.html",
        question=question,
        answer=answer
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------- START ----------------

if __name__ == "__main__":

    create_database()

    app.run(debug=True)