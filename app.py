from flask import Flask, request, redirect, url_for, render_template, jsonify, send_file
import sqlite3
import math
import io
import os
import base64
import cv2
import numpy as np
from openpyxl import Workbook

app = Flask(__name__)
DATABASE = "attendance.db"
FACE_DIR = "faces"
os.makedirs(FACE_DIR, exist_ok=True)

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

NAV = """
<div style="background:#243b55;padding:12px;border-radius:8px;margin-bottom:20px;">
    <a href="/" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Register Student</a>
    <a href="/dashboard" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Dashboard</a>
    <a href="/teacher" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Teacher Portal</a>
    <a href="/student" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Student Portal</a>
    <a href="/parent" style="color:white;margin-right:15px;text-decoration:none;font-weight:bold;">Parent Portal</a>
</div>
"""


@app.route("/")
def home():
    conn = sqlite3.connect(DATABASE)
    students = conn.execute(
        "SELECT student_id, name, department, parent_name, parent_mobile FROM students"
    ).fetchall()
    conn.close()

    rows = ""
    for s in students:
        photo_status = "Registered" if os.path.exists(os.path.join(FACE_DIR, f"{s[0]}_1.jpg")) else "No Photo"
        rows += (
            f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td>"
            f"<td>{s[3] or ''}</td><td>{s[4] or ''}</td><td>{photo_status}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Student Attendance System</title>
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
    {NAV}
    <h1>Student Attendance and Risk Analysis System</h1>
    <div class="box">
        <h2>Register Student &amp; Capture Face</h2>
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

    <h2>Registered Students</h2>
    <table>
        <tr>
            <th>Student ID</th>
            <th>Name</th>
            <th>Department</th>
            <th>Parent Name</th>
            <th>Parent Mobile</th>
            <th>Face Status</th>
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

    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/teacher", methods=["GET", "POST"])
def teacher():
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
    {NAV}
    <h1>Teacher Portal</h1>
    <h2>Create Class Session</h2>
    <form method="POST">
        <input type="text" name="subject" placeholder="Subject Name" required>
        <input type="date" name="session_date" required>
        <input type="time" name="session_time" required>
        <button type="submit">Create Session</button>
    </form>

    <h2>Start Live Browser Face Recognition</h2>
    <form action="/start_attendance" method="POST">
        <select name="session_id" required>
            <option value="">Select Class Session</option>
            {opts}
        </select>
        <button type="submit">Open Camera Scanner</button>
    </form>

    <h2>Sessions &amp; Attendance</h2>
    {session_html}

    <h2>Subject-wise Excel Reports</h2>
    {subject_html}
</body>
</html>"""


@app.route("/start_attendance", methods=["POST"])
def start_attendance():
    session_id = request.form.get("session_id")
    if not session_id:
        return redirect(url_for("teacher"))
    return redirect(url_for("scan_page", session_id=session_id))


@app.route("/scan/<int:session_id>")
def scan_page(session_id):
    return f"""<!DOCTYPE html>
<html>
<head><title>Live Face Attendance</title></head>
<body style="font-family:Arial;text-align:center;padding:30px;background:#f4f6f9;">
    {NAV}
    <h1>Live Face Recognition Scanner (Session {session_id})</h1>
    <video id="video" width="480" height="360" autoplay playsinline style="border:3px solid #243b55;border-radius:10px;"></video>
    <canvas id="canvas" width="480" height="360" style="display:none;"></canvas>
    <h2 id="status" style="color:#243b55;">Starting camera...</h2>
    <p><a href="/teacher">Finish &amp; Return to Teacher Portal</a></p>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const statusEl = document.getElementById('status');

        navigator.mediaDevices.getUserMedia({{ video: true }}).then(stream => {{
            video.srcObject = stream;
            statusEl.innerText = 'Scanning faces every 2 seconds...';
            setInterval(() => {{
                canvas.getContext('2d').drawImage(video, 0, 0, 480, 360);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
                fetch('/api/recognize', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ session_id: {session_id}, image: dataUrl }})
                }}).then(r => r.json()).then(res => {{ statusEl.innerText = res.message; }});
            }}, 2000);
        }}).catch(err => statusEl.innerText = 'Camera error: ' + err);
    </script>
</body>
</html>"""


@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    data = request.get_json()
    session_id = data.get("session_id")
    img_data = data.get("image", "")
    if "," not in img_data:
        return jsonify({"message": "No frame received"})

    detector, recognizer = get_models()
    if detector is None:
        return jsonify({"message": "ONNX models missing on server"})

    img_bytes = base64.b64decode(img_data.split(",", 1)[1])
    frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"message": "Invalid image frame"})

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
        return jsonify({"message": "No registered face photos found. Register a student with camera first."})

    detector.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        conn.close()
        return jsonify({"message": "No face detected in camera..."})

    marked = []
    for f in faces:
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
            marked.append(f"{students[best_id]} ({best_id})")

    conn.commit()
    conn.close()

    if marked:
        return jsonify({"message": "Present Marked: " + ", ".join(marked)})
    return jsonify({"message": "Face detected, but did not match any registered student."})


@app.route("/student")
def student_portal():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    students = conn.execute(
        """
        SELECT s.student_id, s.name, s.department,
               COUNT(ar.record_id) AS total_classes,
               SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM students s
        LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
        GROUP BY s.student_id
        """
    ).fetchall()

    html = (
        f"<html><head><title>Student Portal</title>"
        f"<style>body{{font-family:Arial;background:#f2f2f2;padding:20px;}} "
        f".card{{background:white;padding:20px;margin:15px auto;max-width:550px;border-radius:10px;}}</style>"
        f"</head><body>{NAV}<h1>Student Attendance Portal</h1>"
    )
    for s in students:
        total, present = s["total_classes"], s["present_count"] or 0
        pct = (present / total * 100) if total > 0 else 0
        if total == 0:
            msg, rhtml = "No attendance records available yet.", ""
        elif pct < 75:
            req = math.ceil(3 * total - 4 * present)
            msg = "LOW ATTENDANCE RISK: Below 75%."
            rhtml = (
                f'<div style="background:#ffe0e0;padding:15px;border-radius:8px;color:#a00000;">'
                f'<h3>Attendance Risk Alert!</h3><p>Attend the next <b>{req} consecutive classes</b> to reach 75%.</p></div>'
            )
        else:
            msg, rhtml = "Good! Your attendance is at or above 75%.", '<p style="color:green;">Good attendance!</p>'

        html += (
            f'<div class="card"><h2>{s["name"]}</h2><p>ID: {s["student_id"]} | Dept: {s["department"]}</p>'
            f'<p>Present: {present} / {total} ({pct:.2f}%)</p><p><b>{msg}</b></p>{rhtml}</div>'
        )
    conn.close()
    return html + "</body></html>"


@app.route("/parent")
def parent():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    students = conn.execute(
        """
        SELECT s.student_id, s.name, s.department,
               (SELECT COUNT(*) FROM class_sessions) AS total_classes,
               (SELECT COUNT(*) FROM attendance_records ar WHERE ar.student_id = s.student_id AND ar.status = 'Present') AS present_count
        FROM students s
        """
    ).fetchall()
    conn.close()

    phtml = "".join(
        f'<div style="background:white;padding:20px;margin:15px auto;max-width:450px;border-radius:10px;">'
        f'<h2>{s["name"]}</h2><p>ID: {s["student_id"]} | Dept: {s["department"]}</p>'
        f'<p>Attended: {s["present_count"]} / {s["total_classes"]} '
        f'({(s["present_count"]/s["total_classes"]*100 if s["total_classes"]>0 else 0):.2f}%)</p></div>'
        for s in students
    ) or "<p>No student records available.</p>"

    return (
        f"<!DOCTYPE html><html><head><title>Parent Portal</title></head>"
        f"<body style='font-family:Arial;text-align:center;padding:30px;background:#f0f4f8;'>"
        f"{NAV}<h1>Parent Portal</h1>{phtml}</body></html>"
    )


@app.route("/export_excel/<path:subject>")
def export_excel(subject):
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