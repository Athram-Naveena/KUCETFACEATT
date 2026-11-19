from flask import Flask, request, redirect, url_for, session, jsonify, send_file
import sqlite3
import math
import io
import os
import base64
import cv2
import numpy as np
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kucet_face_att_secret_2026")

DATABASE = "attendance.db"
FACE_DIR = "faces"
os.makedirs(FACE_DIR, exist_ok=True)

DEFAULT_TEACHER_USER = os.environ.get("TEACHER_USER", "admin")
DEFAULT_TEACHER_PASS = os.environ.get("TEACHER_PASS", "kucet123")

DETECTOR_MODEL = "models/face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = "models/face_recognition_sface_2021dec.onnx"


def get_models():
    if os.path.exists(DETECTOR_MODEL) and os.path.exists(RECOGNIZER_MODEL):
        det = cv2.FaceDetectorYN.create(DETECTOR_MODEL, "", (320, 320), 0.7, 0.3, 5000)
        rec = cv2.FaceRecognizerSF.create(RECOGNIZER_MODEL, "")
        return det, rec
    return None, None


def create_database():
    conn = sqlite3.connect(DATABASE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            parent_name TEXT,
            parent_mobile TEXT
        )
    """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()]
    if "parent_name" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN parent_name TEXT")
    if "parent_mobile" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN parent_mobile TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS class_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            session_date TEXT NOT NULL,
            session_time TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Present',
            UNIQUE(session_id, student_id)
        )
    """)
    conn.commit()
    conn.close()


create_database()


def get_nav():
    links = '<a href="/" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Home</a>'
    if session.get("role") == "teacher":
        t_name = session.get("teacher_name", "Teacher")
        links += (
            '<a href="/teacher" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Teacher Portal</a>'
            '<a href="/register_student" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Manage Students</a>'
            f'<a href="/logout" style="color:#ff8a80;text-decoration:none;font-weight:bold;">Logout ({t_name})</a>'
        )
    elif session.get("role") == "parent":
        links += (
            '<a href="/parent" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Parent Dashboard</a>'
            '<a href="/logout" style="color:#ff8a80;text-decoration:none;font-weight:bold;">Logout (Parent)</a>'
        )
    else:
        links += (
            '<a href="/teacher_login" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Teacher Login</a>'
            '<a href="/teacher_register" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Teacher Register</a>'
            '<a href="/parent_login" style="color:white;text-decoration:none;font-weight:bold;">Parent Login</a>'
        )
    return f'<div style="background:#243b55;padding:12px;border-radius:8px;margin-bottom:20px;text-align:center;">{links}</div>'


@app.route("/")
def home():
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>KUCET Face Attendance System</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f0f4f8; padding: 30px; text-align: center; }}
        h1 {{ color: #243b55; }}
        .container {{ display: flex; justify-content: center; flex-wrap: wrap; gap: 25px; margin-top: 30px; }}
        .portal {{ background: white; padding: 30px; width: 260px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .btn {{ display: inline-block; background: #243b55; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 6px 4px; }}
        .btn-outline {{ display: inline-block; background: #198754; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 6px 4px; }}
    </style>
</head>
<body>
    {get_nav()}
    <h1>Student Attendance and Risk Analysis System</h1>
    <p>Select your portal to continue</p>
    <div class="container">
        <div class="portal">
            <h2>Teacher Portal</h2>
            <p>Register faculty account, manage students, scan class faces, and export reports.</p>
            <a class="btn" href="/teacher_login">Teacher Login</a>
            <a class="btn-outline" href="/teacher_register">New Teacher</a>
        </div>
        <div class="portal">
            <h2>Parent Portal</h2>
            <p>Log in with your registered mobile number and student ID to view attendance.</p>
            <a class="btn" href="/parent_login">Parent Login</a>
        </div>
    </div>
</body>
</html>"""


@app.route("/teacher_register", methods=["GET", "POST"])
def teacher_register():
    error = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not all([name, department, username, password]):
            error = "<p style='color:red;'>All fields are required.</p>"
        else:
            conn = sqlite3.connect(DATABASE)
            try:
                conn.execute(
                    "INSERT INTO teachers (name, department, username, password) VALUES (?, ?, ?, ?)",
                    (name, department, username, password),
                )
                conn.commit()
                conn.close()
                return redirect(url_for("teacher_login"))
            except sqlite3.IntegrityError:
                conn.close()
                error = "<p style='color:red;'>Username already taken. Choose another.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><title>Register New Teacher</title></head>
<body style="font-family:Arial;background:#f0f4f8;padding:30px;text-align:center;">
    {get_nav()}
    <div style="background:white;padding:30px;max-width:400px;margin:30px auto;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h2>Register New Teacher</h2>
        {error}
        <form method="POST">
            <input type="text" name="name" placeholder="Full Name (e.g. Dr. R. Kumar)" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <input type="text" name="department" placeholder="Department (e.g. ECE)" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <input type="text" name="username" placeholder="Create Username" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <input type="password" name="password" placeholder="Create Password" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <button type="submit" style="background:#198754;color:white;padding:10px 25px;border:none;border-radius:6px;cursor:pointer;margin-top:10px;">Create Teacher Account</button>
        </form>
        <p style="margin-top:15px;">Already registered? <a href="/teacher_login">Login here</a></p>
    </div>
</body>
</html>"""


@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():
    if session.get("role") == "teacher":
        return redirect(url_for("teacher"))
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == DEFAULT_TEACHER_USER and password == DEFAULT_TEACHER_PASS:
            session["role"] = "teacher"
            session["teacher_name"] = "Admin"
            return redirect(url_for("teacher"))

        conn = sqlite3.connect(DATABASE)
        row = conn.execute(
            "SELECT name FROM teachers WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        conn.close()

        if row:
            session["role"] = "teacher"
            session["teacher_name"] = row[0]
            return redirect(url_for("teacher"))
        error = "<p style='color:red;'>Invalid Teacher Username or Password.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><title>Teacher Login</title></head>
<body style="font-family:Arial;background:#f0f4f8;padding:30px;text-align:center;">
    {get_nav()}
    <div style="background:white;padding:30px;max-width:380px;margin:30px auto;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h2>Teacher Login</h2>
        {error}
        <form method="POST">
            <input type="text" name="username" placeholder="Teacher Username" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <input type="password" name="password" placeholder="Password" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <button type="submit" style="background:#243b55;color:white;padding:10px 25px;border:none;border-radius:6px;cursor:pointer;margin-top:10px;">Login</button>
        </form>
        <p style="margin-top:15px;">New faculty member? <a href="/teacher_register">Register here</a></p>
    </div>
</body>
</html>"""


@app.route("/parent_login", methods=["GET", "POST"])
def parent_login():
    if session.get("role") == "parent":
        return redirect(url_for("parent"))
    error = ""
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        parent_mobile = request.form.get("parent_mobile", "").strip()
        conn = sqlite3.connect(DATABASE)
        student = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ? AND parent_mobile = ?",
            (student_id, parent_mobile),
        ).fetchone()
        conn.close()
        if student:
            session["role"] = "parent"
            session["student_id"] = student_id
            return redirect(url_for("parent"))
        error = "<p style='color:red;'>No matching Student ID and Parent Mobile found.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><title>Parent Login</title></head>
<body style="font-family:Arial;background:#f0f4f8;padding:30px;text-align:center;">
    {get_nav()}
    <div style="background:white;padding:30px;max-width:380px;margin:30px auto;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h2>Parent Login</h2>
        <p style="font-size:13px;color:#555;">Enter your registered Parent Mobile Number and your child's Student ID.</p>
        {error}
        <form method="POST">
            <input type="text" name="student_id" placeholder="Student ID (e.g. 23567T1554)" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <input type="text" name="parent_mobile" placeholder="Registered Parent Mobile Number" required style="width:90%;padding:10px;margin:8px 0;"><br>
            <button type="submit" style="background:#243b55;color:white;padding:10px 25px;border:none;border-radius:6px;cursor:pointer;margin-top:10px;">View Child Attendance</button>
        </form>
    </div>
</body>
</html>"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/register_student")
def register_student():
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))

    conn = sqlite3.connect(DATABASE)
    students = conn.execute(
        "SELECT student_id, name, department, parent_name, parent_mobile FROM students ORDER BY student_id"
    ).fetchall()
    conn.close()

    rows = ""
    for s in students:
        safe_id = "".join(c for c in s[0] if c.isalnum() or c in "-_")
        photo_status = "Registered" if os.path.exists(os.path.join(FACE_DIR, f"{safe_id}_1.jpg")) else "No Photo"
        rows += (
            f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td>"
            f"<td>{s[3] or ''}</td><td>{s[4] or ''}</td><td>{photo_status}</td>"
            f"<td><form method='POST' action='/delete_student' onsubmit=\"return confirm('Remove passed-out student {s[1]} ({s[0]}) and all their records?');\">"
            f"<input type='hidden' name='student_id' value='{s[0]}'>"
            f"<button type='submit' style='background:#d32f2f;color:white;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;'>Remove</button>"
            f"</form></td></tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Manage &amp; Register Students</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; background: #f4f6f9; }}
        h1 {{ color: #243b55; }}
        .box {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; }}
        input {{ padding: 10px; margin: 5px; }}
        button {{ padding: 10px 18px; background: #243b55; color: white; border: none; border-radius: 5px; cursor: pointer; }}
        table {{ border-collapse: collapse; width: 100%; background: white; }}
        th, td {{ padding: 12px; border: 1px solid #ddd; text-align: left; }}
    </style>
</head>
<body>
    {get_nav()}
    <h1>Manage Students (Register New / Remove Passed-Out)</h1>
    <div class="box">
        <h2>Register New Student &amp; Capture Face</h2>
        <form id="regForm" method="POST" action="/register">
            <input name="student_id" placeholder="Student ID" required>
            <input name="name" placeholder="Student Name" required>
            <input name="department" placeholder="Department" required>
            <input name="parent_name" placeholder="Parent Name" required>
            <input name="parent_mobile" placeholder="Parent Mobile Number" required>
            <input type="hidden" name="face_image" id="face_image">
            <div style="margin:15px 0;">
                <video id="video" width="320" height="240" autoplay playsinline style="border:2px solid #243b55;border-radius:8px;"></video>
                <canvas id="canvas" width="320" height="240" style="display:none;"></canvas><br>
                <button type="button" onclick="captureAndSubmit()">Capture Face &amp; Register Student</button>
                <p id="camStatus" style="color:#555;">Allow camera access to capture student face during registration.</p>
            </div>
        </form>
    </div>

    <h2>Enrolled Students ({len(students)})</h2>
    <table>
        <tr>
            <th>Student ID</th>
            <th>Name</th>
            <th>Department</th>
            <th>Parent Name</th>
            <th>Parent Mobile</th>
            <th>Face Status</th>
            <th>Action</th>
        </tr>
        {rows}
    </table>

    <script>
        const video = document.getElementById('video');
        navigator.mediaDevices.getUserMedia({{ video: true }})
            .then(s => video.srcObject = s)
            .catch(e => document.getElementById('camStatus').innerText = 'Camera blocked: ' + e);

        function captureAndSubmit() {{
            const form = document.getElementById('regForm');
            if (!form.reportValidity()) return;
            const canvas = document.getElementById('canvas');
            canvas.getContext('2d').drawImage(video, 0, 0, 320, 240);
            document.getElementById('face_image').value = canvas.toDataURL('image/jpeg', 0.9);
            form.submit();
        }}
    </script>
</body>
</html>"""


@app.route("/register", methods=["POST"])
def register():
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))

    student_id = request.form["student_id"].strip()
    name = request.form["name"].strip()
    department = request.form["department"].strip()
    parent_name = request.form["parent_name"].strip()
    parent_mobile = request.form["parent_mobile"].strip()
    face_data = request.form.get("face_image", "")

    if not all([student_id, name, department, parent_name, parent_mobile]):
        return "Please fill in all fields.", 400

    conn = sqlite3.connect(DATABASE)
    exists = conn.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if exists:
        conn.execute(
            "UPDATE students SET name=?, department=?, parent_name=?, parent_mobile=? WHERE student_id=?",
            (name, department, parent_name, parent_mobile, student_id),
        )
    else:
        conn.execute(
            "INSERT INTO students (student_id, name, department, parent_name, parent_mobile) VALUES (?, ?, ?, ?, ?)",
            (student_id, name, department, parent_name, parent_mobile),
        )
    conn.commit()
    conn.close()

    if "," in face_data:
        img_bytes = base64.b64decode(face_data.split(",", 1)[1])
        safe_id = "".join(c for c in student_id if c.isalnum() or c in "-_")
        with open(os.path.join(FACE_DIR, f"{safe_id}_1.jpg"), "wb") as f:
            f.write(img_bytes)

    return redirect(url_for("register_student"))


@app.route("/delete_student", methods=["POST"])
def delete_student():
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))

    student_id = request.form.get("student_id", "").strip()
    if student_id:
        conn = sqlite3.connect(DATABASE)
        conn.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
        conn.close()

        safe_id = "".join(c for c in student_id if c.isalnum() or c in "-_")
        for fn in os.listdir(FACE_DIR):
            if fn.startswith(f"{safe_id}_"):
                try:
                    os.remove(os.path.join(FACE_DIR, fn))
                except OSError:
                    pass

    return redirect(url_for("register_student"))


@app.route("/teacher", methods=["GET", "POST"])
def teacher():
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))

    if request.method == "POST":
        action = request.form.get("action")
        conn = sqlite3.connect(DATABASE)
        if action == "mark_absent":
            sid = request.form["session_id"]
            conn.execute(
                """
                INSERT OR IGNORE INTO attendance_records (session_id, student_id, status)
                SELECT ?, s.student_id, 'Absent' FROM students s
                WHERE NOT EXISTS (
                    SELECT 1 FROM attendance_records a
                    WHERE a.session_id = ? AND a.student_id = s.student_id
                )
                """,
                (sid, sid),
            )
        else:
            conn.execute(
                "INSERT INTO class_sessions (subject, session_date, session_time) VALUES (?, ?, ?)",
                (request.form["subject"].strip(), request.form["session_date"], request.form["session_time"]),
            )
        conn.commit()
        conn.close()
        return redirect(url_for("teacher"))

    conn = sqlite3.connect(DATABASE)
    sessions = conn.execute("SELECT * FROM class_sessions ORDER BY session_id DESC").fetchall()
    subjects = sorted(set(s[1] for s in sessions))

    subject_html = "".join(
        f'<div style="border:1px solid #198754;padding:15px;margin:15px;border-radius:8px;background:white;">'
        f'<h3>{sub}</h3><a href="{url_for("export_excel", subject=sub)}">Download {sub} Excel</a></div>'
        for sub in subjects
    )

    session_html = ""
    for s in sessions:
        recs = conn.execute(
            """
            SELECT students.student_id, students.name, attendance_records.status
            FROM attendance_records
            JOIN students ON attendance_records.student_id = students.student_id
            WHERE attendance_records.session_id = ?
            """,
            (s[0],),
        ).fetchall()
        att_html = "".join(f"<p>{r[0]} | {r[1]} | {r[2]}</p>" for r in recs) or "<p>No attendance recorded yet.</p>"
        p_cnt = sum(1 for r in recs if r[2] == "Present")
        a_cnt = sum(1 for r in recs if r[2] == "Absent")
        session_html += (
            f'<div style="border:1px solid #ccc;padding:15px;margin:15px;background:white;border-radius:8px;">'
            f'<h3>{s[1]} (Session {s[0]})</h3><p>Date: {s[2]} | Time: {s[3]}</p>{att_html}'
            f'<p>Present: {p_cnt} | Absent: {a_cnt}</p>'
            f'<form method="POST"><input type="hidden" name="session_id" value="{s[0]}">'
            f'<input type="hidden" name="action" value="mark_absent">'
            f'<button type="submit">Mark Remaining Students Absent</button></form></div>'
        )
    conn.close()

    opts = "".join(f'<option value="{s[0]}">{s[1]} - {s[2]} - {s[3]}</option>' for s in sessions)
    return f"""<html>
<head><title>Teacher Portal</title></head>
<body style="font-family:Arial;text-align:center;padding:30px;background:#f4f6f9;">
    {get_nav()}
    <h1>Teacher Portal — Welcome, {session.get('teacher_name', 'Teacher')}</h1>
    <p><a href="/register_student" style="background:#198754;color:white;padding:10px 18px;text-decoration:none;border-radius:6px;font-weight:bold;">Manage Students (Add New / Remove Passed-Out)</a></p>

    <h2>Create Class Session</h2>
    <form method="POST">
        <input type="text" name="subject" placeholder="Subject Name" required>
        <input type="date" name="session_date" required>
        <input type="time" name="session_time" required>
        <button type="submit">Create Session</button>
    </form>

    <h2>Start Multi-Student Face Recognition</h2>
    <form action="/start_attendance" method="POST">
        <select name="session_id" required>
            <option value="">Select Class Session</option>
            {opts}
        </select>
        <button type="submit">Open HD Camera Scanner</button>
    </form>

    <h2>Sessions &amp; Attendance</h2>
    {session_html}

    <h2>Subject-wise Excel Reports</h2>
    {subject_html}
</body>
</html>"""


@app.route("/start_attendance", methods=["POST"])
def start_attendance():
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))
    session_id = request.form.get("session_id")
    if not session_id:
        return redirect(url_for("teacher"))
    return redirect(url_for("scan_page", session_id=session_id))


@app.route("/scan/<int:session_id>")
def scan_page(session_id):
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))
    return f"""<!DOCTYPE html>
<html>
<head><title>Live Multi-Student Face Attendance</title></head>
<body style="font-family:Arial;text-align:center;padding:20px;background:#f4f6f9;">
    {get_nav()}
    <h1>Multi-Student Face Scanner (Session {session_id})</h1>
    <div style="position:relative;display:inline-block;">
        <video id="video" width="640" height="480" autoplay playsinline style="border:3px solid #243b55;border-radius:10px;"></video>
        <canvas id="overlay" width="640" height="480" style="position:absolute;left:0;top:0;pointer-events:none;"></canvas>
    </div>
    <canvas id="capture" width="1280" height="720" style="display:none;"></canvas>
    <h2 id="status" style="color:#243b55;">Starting HD camera...</h2>
    <p><a href="/teacher">Finish &amp; Return to Teacher Portal</a></p>

    <script>
        const video = document.getElementById('video');
        const overlay = document.getElementById('overlay');
        const capture = document.getElementById('capture');
        const statusEl = document.getElementById('status');
        const octx = overlay.getContext('2d');

        navigator.mediaDevices.getUserMedia({{ video: {{ width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }} }}).then(stream => {{
            video.srcObject = stream;
            statusEl.innerText = 'Scanning all faces in frame every 2 seconds...';
            setInterval(() => {{
                capture.getContext('2d').drawImage(video, 0, 0, 1280, 720);
                const dataUrl = capture.toDataURL('image/jpeg', 0.85);
                fetch('/api/recognize', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ session_id: {session_id}, image: dataUrl }})
                }}).then(r => r.json()).then(res => {{
                    statusEl.innerText = res.message;
                    octx.clearRect(0, 0, overlay.width, overlay.height);
                    if (res.boxes) {{
                        const sx = overlay.width / 1280;
                        const sy = overlay.height / 720;
                        res.boxes.forEach(b => {{
                            octx.strokeStyle = b.matched ? '#00c853' : '#ff1744';
                            octx.lineWidth = 3;
                            octx.strokeRect(b.x * sx, b.y * sy, b.w * sx, b.h * sy);
                            octx.fillStyle = b.matched ? '#00c853' : '#ff1744';
                            octx.font = 'bold 14px Arial';
                            octx.fillText(b.label, b.x * sx, Math.max(16, b.y * sy - 6));
                        }});
                    }}
                }});
            }}, 2000);
        }}).catch(err => statusEl.innerText = 'Camera error: ' + err);
    </script>
</body>
</html>"""


@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    if session.get("role") != "teacher":
        return jsonify({"message": "Unauthorized", "boxes": []}), 403

    data = request.get_json()
    session_id = data.get("session_id")
    img_data = data.get("image", "")
    if "," not in img_data:
        return jsonify({"message": "No frame received", "boxes": []})

    detector, recognizer = get_models()
    if detector is None:
        return jsonify({"message": "ONNX models missing on server", "boxes": []})

    img_bytes = base64.b64decode(img_data.split(",", 1)[1])
    frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"message": "Invalid image frame", "boxes": []})

    conn = sqlite3.connect(DATABASE)
    students = dict(conn.execute("SELECT student_id, name FROM students").fetchall())
    known = {}

    for fn in os.listdir(FACE_DIR):
        if not fn.lower().endswith(".jpg"):
            continue
        sid = fn.rsplit("_", 1)[0]
        if sid not in students:
            continue
        ref = cv2.imread(os.path.join(FACE_DIR, fn))
        if ref is None:
            continue
        detector.setInputSize((ref.shape[1], ref.shape[0]))
        _, rfaces = detector.detect(ref)
        if rfaces is not None and len(rfaces) >= 1:
            known.setdefault(sid, []).append(recognizer.feature(recognizer.alignCrop(ref, rfaces[0])))

    if not known:
        conn.close()
        return jsonify({"message": "No registered face photos found.", "boxes": []})

    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        conn.close()
        return jsonify({"message": "No faces detected in frame...", "boxes": []})

    marked = []
    boxes = []
    for f in faces:
        x, y, w, h = map(int, f[:4])
        feat = recognizer.feature(recognizer.alignCrop(frame, f))
        best_id, best_score = None, -1.0
        for sid, feats in known.items():
            score = max(recognizer.match(feat, sf, cv2.FaceRecognizerSF_FR_COSINE) for sf in feats)
            if score > best_score:
                best_score, best_id = score, sid
        if best_score >= 0.363 and best_id:
            conn.execute(
                "INSERT OR IGNORE INTO attendance_records (session_id, student_id, status) VALUES (?, ?, 'Present')",
                (session_id, best_id),
            )
            label = f"{students[best_id]} ({best_score:.2f})"
            marked.append(f"{students[best_id]} ({best_id})")
            boxes.append({"x": x, "y": y, "w": w, "h": h, "label": label, "matched": True})
        else:
            boxes.append({"x": x, "y": y, "w": w, "h": h, "label": f"Unknown ({best_score:.2f})", "matched": False})

    conn.commit()
    conn.close()

    msg = f"Detected {len(faces)} face(s) | Marked Present: {', '.join(marked)}" if marked else f"Detected {len(faces)} face(s), none matched yet."
    return jsonify({"message": msg, "boxes": boxes})


@app.route("/parent")
def parent():
    if session.get("role") != "parent" or not session.get("student_id"):
        return redirect(url_for("parent_login"))

    sid = session["student_id"]
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    s = conn.execute(
        """
        SELECT s.student_id, s.name, s.department, s.parent_name,
               COUNT(ar.record_id) AS total_classes,
               SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM students s
        LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
        WHERE s.student_id = ?
        GROUP BY s.student_id
        """,
        (sid,),
    ).fetchone()

    subject_records = conn.execute(
        """
        SELECT cs.subject,
               COUNT(ar.record_id) AS total,
               SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) AS present
        FROM attendance_records ar
        JOIN class_sessions cs ON ar.session_id = cs.session_id
        WHERE ar.student_id = ?
        GROUP BY cs.subject
        """,
        (sid,),
    ).fetchall()
    conn.close()

    if not s:
        session.clear()
        return redirect(url_for("parent_login"))

    total = s["total_classes"]
    present = s["present_count"] or 0
    absent = total - present
    pct = (present / total * 100) if total > 0 else 0

    if total == 0:
        alert_html = "<p>No class sessions recorded yet.</p>"
    elif pct < 75:
        req = math.ceil(3 * total - 4 * present)
        alert_html = (
            f'<div style="background:#ffe0e0;padding:15px;border-radius:8px;color:#a00000;margin:15px 0;">'
            f'<h3>Low Attendance Alert (Below 75%)</h3>'
            f'<p>Your child must attend the next <b>{req} consecutive classes</b> to reach 75%.</p></div>'
        )
    else:
        alert_html = '<p style="color:green;font-weight:bold;">Good Standing: Attendance is 75% or above.</p>'

    sub_html = "".join(
        f"<p><b>{r['subject']}:</b> {(r['present']/r['total']*100 if r['total']>0 else 0):.2f}% ({r['present']}/{r['total']})</p>"
        for r in subject_records
    ) or "<p>No subject records yet.</p>"

    return f"""<!DOCTYPE html>
<html>
<head><title>Parent Portal</title></head>
<body style="font-family:Arial;text-align:center;padding:30px;background:#f0f4f8;">
    {get_nav()}
    <h1>Parent Attendance Dashboard</h1>
    <div style="background:white;padding:25px;margin:20px auto;max-width:480px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h2>{s['name']}</h2>
        <p><b>Student ID:</b> {s['student_id']} | <b>Department:</b> {s['department']}</p>
        <p><b>Parent:</b> {s['parent_name'] or ''}</p>
        <hr>
        <p><b>Total Classes:</b> {total} | <b>Present:</b> {present} | <b>Absent:</b> {absent}</p>
        <h2>Overall Attendance: {pct:.2f}%</h2>
        {alert_html}
        <hr>
        <h3>Subject-wise Breakdown</h3>
        {sub_html}
    </div>
</body>
</html>"""


@app.route("/export_excel/<path:subject>")
def export_excel(subject):
    if session.get("role") != "teacher":
        return redirect(url_for("teacher_login"))

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    records = conn.execute(
        """
        SELECT s.student_id, s.name, s.department,
               COUNT(DISTINCT cs.session_id) AS total,
               COALESCE(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END), 0) AS present
        FROM students s
        CROSS JOIN class_sessions cs
        LEFT JOIN attendance_records ar ON ar.student_id = s.student_id AND ar.session_id = cs.session_id
        WHERE cs.subject = ?
        GROUP BY s.student_id, s.name, s.department
        ORDER BY s.student_id
        """,
        (subject,),
    ).fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.append([
        "Student ID", "Student Name", "Department",
        "Present Classes", "Absent Classes", "Total Classes",
        "Attendance Percentage", "Risk Status"
    ])
    for r in records:
        t, p = r["total"] or 0, r["present"] or 0
        pct = p / t * 100 if t > 0 else 0
        ws.append([
            r["student_id"], r["name"], r["department"],
            p, t - p, t, round(pct, 2),
            "Below 75% - At Risk" if (t > 0 and pct < 75) else "Good"
        ])

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(
        out,
        as_attachment=True,
        download_name=f"{subject}_Attendance.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True)