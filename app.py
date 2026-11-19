from flask import Flask, request, redirect, url_for, render_template
import sqlite3
import subprocess
import sys
import math
import io
import os
from flask import send_file
from openpyxl import Workbook
app = Flask(__name__)

DATABASE = "attendance.db" 


def create_database():
    connection = sqlite3.connect(DATABASE)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL
        )
    """)
    columns = [
        row[1] for row in connection.execute(
            "PRAGMA table_info(students)"
        ).fetchall()
    ]

    if "parent_name" not in columns:
        connection.execute(
            "ALTER TABLE students ADD COLUMN parent_name TEXT"
        )

    if "parent_mobile" not in columns:
        connection.execute(
            "ALTER TABLE students ADD COLUMN parent_mobile TEXT"
        )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            attendance_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Present',
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, attendance_date)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS class_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            session_date TEXT NOT NULL,
            session_time TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Present',
            FOREIGN KEY (session_id) REFERENCES class_sessions(session_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(session_id, student_id)
        )
    """)

    connection.commit()
    connection.close()

create_database()

@app.route("/")
def home():
    connection = sqlite3.connect(DATABASE)
    students = connection.execute(
    """
    SELECT student_id, name, department,
           parent_name, parent_mobile
    FROM students
    """
).fetchall()
    connection.close()

    rows = ""

    for student in students:
      rows += (
        f"<tr><td>{student[0]}</td>"
        f"<td>{student[1]}</td>"
        f"<td>{student[2]}</td>"
        f"<td>{student[3] or ''}</td>"
        f"<td>{student[4] or ''}</td></tr>"
     )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Student Attendance System</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f4f6f9;
            }}
            h1 {{ color: #243b55; }}
            form, table {{
                background: white;
                padding: 20px;
                margin-bottom: 25px;
            }}
            input {{
                padding: 10px;
                margin: 5px;
            }}
            button {{
                padding: 10px 18px;
                cursor: pointer;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }}
        </style>
    </head>
    <body>
        <div style="background:#243b55;padding:12px;border-radius:8px;margin-bottom:20px;"><a href="/dashboard" style="color:white;margin-right:15px;">Dashboard</a><a href="/teacher" style="color:white;margin-right:15px;">Teacher Portal</a><a href="/student" style="color:white;margin-right:15px;">Student Portal</a><a href="/parent" style="color:white;margin-right:15px;">Parent Portal</a><a href="/attendance" style="color:white;">Attendance</a></div>
<h1>Student Attendance and Risk Analysis System</h1>

        <h2>Register Student</h2>

        <form method="POST" action="/register">
            <input name="student_id"
                   placeholder="Student ID" required>

            <input name="name"
                   placeholder="Student Name" required>

           <input name="department"
       placeholder="Department" required>

    <input name="parent_name"
       placeholder="Parent Name" required>

    <input name="parent_mobile"
       placeholder="Parent Mobile Number" required>

    <button type="submit">Register Student</button>
        </form>

        <h2>Registered Students</h2>

        <table>
            <tr>
                <th>Student ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Parent Name</th>
                <th>Parent Mobile</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """


@app.route("/register", methods=["POST"])
def register():
    student_id = request.form["student_id"].strip()
    name = request.form["name"].strip()
    department = request.form["department"].strip()
    parent_name = request.form["parent_name"].strip()
    parent_mobile = request.form["parent_mobile"].strip()

    if not student_id or not name or not department or not parent_name or not parent_mobile:
        return "Please fill in all fields.", 400

    connection = sqlite3.connect(DATABASE)

    existing_student = connection.execute(
        "SELECT student_id FROM students WHERE student_id = ?",
        (student_id,)
    ).fetchone()

    if existing_student:
        connection.execute(
            """
            UPDATE students
            SET parent_name = ?, parent_mobile = ?
            WHERE student_id = ?
            """,
            (parent_name, parent_mobile, student_id)
        )
    else:
        connection.execute(
            """
            INSERT INTO students
            (student_id, name, department, parent_name, parent_mobile)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, name, department, parent_name, parent_mobile)
        )

    connection.commit()
    connection.close()

    return redirect(url_for("home"))
    connection.close()

    return redirect(url_for("home"))
@app.route("/attendance")
def attendance_page():
    connection = sqlite3.connect(DATABASE)

    records = connection.execute("""
        SELECT attendance.student_id,
               students.name,
               attendance.attendance_date,
               attendance.attendance_time,
               attendance.status
        FROM attendance
        LEFT JOIN students
        ON attendance.student_id = students.student_id
        ORDER BY attendance.attendance_date DESC,
                 attendance.attendance_time DESC
    """).fetchall()

    connection.close()

    rows = ""

    for record in records:
        rows += f"""
        <tr>
            <td>{record[0]}</td>
            <td>{record[1] or 'Unknown'}</td>
            <td>{record[2]}</td>
            <td>{record[3]}</td>
            <td>{record[4]}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Attendance Records</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f4f6f9;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
            }}
            th, td {{
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background: #243b55;
                color: white;
            }}
        </style>
    </head>
    <body>
        <h1>Student Attendance Records</h1>
        <table>
            <tr>
                <th>Student ID</th>
                <th>Name</th>
                <th>Date</th>
                <th>Time</th>
                <th>Status</th>
            </tr>
            {rows}
        </table>
        <p><a href="/">Back to Student Registration</a></p>
    </body>
    </html>
    """
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/teacher", methods=["GET", "POST"])
def teacher():

    if request.method == "POST":

        action = request.form.get("action")
        connection = sqlite3.connect(DATABASE)

        if action == "mark_absent":
            session_id = request.form["session_id"]

            connection.execute("""
                INSERT OR IGNORE INTO attendance_records
                (session_id, student_id, status)
                SELECT ?, s.student_id, 'Absent'
                FROM students s
                WHERE NOT EXISTS (
                    SELECT 1 FROM attendance_records a
                    WHERE a.session_id = ?
                    AND a.student_id = s.student_id
                )
            """, (session_id, session_id))

        else:
            subject = request.form["subject"].strip()
            session_date = request.form["session_date"]
            session_time = request.form["session_time"]

            connection.execute("""
                INSERT INTO class_sessions
                (subject, session_date, session_time)
                VALUES (?, ?, ?)
            """, (subject, session_date, session_time))

        connection.commit()
        connection.close()

        return redirect(url_for("teacher"))

    connection = sqlite3.connect(DATABASE)

    sessions = connection.execute("""
        SELECT * FROM class_sessions
        ORDER BY session_id DESC
    """).fetchall()

    session_html = ""
    subject_html = ""

    subjects = sorted(set(s[1] for s in sessions))

    for subject in subjects:
        download_url = url_for("export_excel", subject=subject)

        subject_html += f"""
            <div style="border:1px solid #198754;
                        padding:15px;margin:15px;border-radius:8px;">
                <h3>{subject}</h3>
                <a href="{download_url}">
                    Download {subject} Excel
                </a>
            </div>
        """

    for s in sessions:

        records = connection.execute("""
            SELECT students.student_id, students.name,
                   attendance_records.status
            FROM attendance_records
            JOIN students
            ON attendance_records.student_id = students.student_id
            WHERE attendance_records.session_id = ?
        """, (s[0],)).fetchall()

        attendance_html = ""

        for record in records:
            attendance_html += f"""
                <p>{record[0]} | {record[1]} | {record[2]}</p>
            """

        if not records:
            attendance_html = "<p>No attendance recorded yet.</p>"

        present_count = sum(
            1 for r in records if r[2] == "Present"
        )

        absent_count = sum(
            1 for r in records if r[2] == "Absent"
        )

        session_html += f"""
            <div style="border:1px solid #ccc;padding:15px;margin:15px;">
                <h3>{s[1]}</h3>
                <p>Session ID: {s[0]}</p>
                <p>Date: {s[2]} | Time: {s[3]}</p>

                <h4>Attendance Records</h4>
                {attendance_html}

                <p>Total Present: {present_count}</p>
                <p>Total Absent: {absent_count}</p>

                <form method="POST">
                    <input type="hidden" name="session_id"
                           value="{s[0]}">
                    <input type="hidden" name="action"
                           value="mark_absent">
                    <button type="submit">
                        Mark Remaining Students Absent
                    </button>
                </form>
            </div>
        """

    connection.close()

    return f"""
    <html>
    <head>
        <title>Teacher Portal</title>
    </head>

    <body style="font-family:Arial;text-align:center;padding:30px;">

        <h1>Teacher Portal</h1>

        <h2>Create Class Session</h2>

        <form method="POST">
            <input type="text" name="subject"
                   placeholder="Subject Name" required>
            <br><br>

            <input type="date" name="session_date" required>
            <br><br>

            <input type="time" name="session_time" required>
            <br><br>

            <button type="submit">Create Session</button>
        </form>

        
        <h2>Start Face Recognition Attendance</h2>

<form action="/start_attendance" method="POST">

    <select name="session_id" required>
        <option value="">Select Class Session</option>
        {''.join(
            f'<option value="{s[0]}">{s[1]} - {s[2]} - {s[3]}</option>'
            for s in sessions
        )}
    </select>

    <br><br>

    <button type="submit">Start Face Recognition</button>

</form>

<h2>Subject-wise Excel Reports</h2>

{subject_html}
        <br>
        <a href="/dashboard">Back to Dashboard</a>

    </body>
    </html>
    """
@app.route("/start_attendance", methods=["POST"])
def start_attendance():

    session_id = request.form.get("session_id")

    if not session_id:
        return redirect(url_for("teacher"))

    connection = sqlite3.connect(DATABASE)

    session = connection.execute(
        "SELECT session_id FROM class_sessions WHERE session_id = ?",
        (session_id,)
    ).fetchone()

    connection.close()

    if session is None:
        return redirect(url_for("teacher"))

    subprocess.Popen(
    [sys.executable, "recognize_faces.py", str(session_id)],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
)

    return redirect(url_for("teacher"))
@app.route("/student")
def student_portal():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    students = connection.execute("""
        SELECT
            s.student_id,
            s.name,
            s.department,
            COUNT(ar.record_id) AS total_classes,
            SUM(
                CASE WHEN ar.status = 'Present'
                THEN 1 ELSE 0 END
            ) AS present_count
        FROM students s
        LEFT JOIN attendance_records ar
            ON s.student_id = ar.student_id
        GROUP BY s.student_id
    """).fetchall()

    student_html = """
    <html>
    <head>
        <title>Student Portal</title>
        <style>
            body {
                font-family: Arial;
                background: #f2f2f2;
                padding: 20px;
            }
            .card {
                background: white;
                padding: 20px;
                margin: 15px auto;
                max-width: 550px;
                border-radius: 10px;
            }
        </style>
    </head>
    <body>
        <h1>Student Attendance Portal</h1>
    """

    for s in students:
        total = s["total_classes"]
        present = s["present_count"] or 0

        percentage = (
            present / total * 100 if total > 0 else 0
        )

        if total == 0:
          message = "No attendance records available yet."
          risk_html = ""

        elif percentage < 75:
           required_classes = math.ceil(3 * total - 4 * present)

           message = "LOW ATTENDANCE RISK: Below 75%."

           risk_html = f"""
        <div style="background:#ffe0e0; padding:15px;
                    border-radius:8px; color:#a00000;">
            <h3>Attendance Risk Alert!</h3>
            <p>Your attendance is below 75%.</p>
            <p>You must attend the next
            <b>{required_classes} consecutive classes</b>
            to reach 75%.</p>
        </div>
        """

        else:
            message = "Good! Your attendance is at or above 75%."
            risk_html = """
        <p style="color:green;">
            Good attendance! You are meeting the 75% requirement.
        </p>
        """
        subject_records = connection.execute("""
            SELECT
                cs.subject,
                COUNT(ar.record_id) AS total,
                SUM(
                    CASE WHEN ar.status = 'Present'
                    THEN 1 ELSE 0 END
                ) AS present
            FROM attendance_records ar
            JOIN class_sessions cs
                ON ar.session_id = cs.session_id
            WHERE ar.student_id = ?
            GROUP BY cs.subject
        """, (s["student_id"],)).fetchall()

        subject_html = "<h3>Subject-wise Attendance</h3>"

        if not subject_records:
            subject_html += "<p>No subject records available.</p>"

        for subject in subject_records:
            subject_total = subject["total"]
            subject_present = subject["present"] or 0

            subject_percentage = (
                subject_present / subject_total * 100
                if subject_total > 0 else 0
            )

            subject_html += f"""
                <p>
                    {subject['subject']}: 
                    {subject_percentage:.2f}%
                    ({subject_present}/{subject_total})
                </p>
            """

        student_html += f"""
        <div class="card">
            <h2>{s['name']}</h2>
            <p>Student ID: {s['student_id']}</p>
            <p>Department: {s['department']}</p>

            <h3>Overall Attendance</h3>
            <p>Present Classes: {present}</p>
            <p>Total Recorded Classes: {total}</p>
            <h2>{percentage:.2f}%</h2>

            <p><b>{message}</b></p>

{risk_html}

{subject_html}
        </div>
        """

    connection.close()

    if not students:
        student_html += "<p>No students registered yet.</p>"

    student_html += """
    </body>
    </html>
    """

    return student_html
@app.route("/parent")
def parent():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    students = connection.execute("""
        SELECT
            s.student_id,
            s.name,
            s.department,
            (SELECT COUNT(*)
             FROM class_sessions) AS total_classes,
            (SELECT COUNT(*)
             FROM attendance_records ar
             WHERE ar.student_id = s.student_id
             AND ar.status = 'Present') AS present_count
        FROM students s
    """).fetchall()

    connection.close()

    parent_html = ""

    for s in students:
        total = s["total_classes"]
        present = s["present_count"]
        absent = total - present

        percentage = (present / total * 100) if total > 0 else 0

        if total == 0:
            message = "No class sessions available yet."
        elif percentage < 75:
            message = "Warning: Your child has low attendance."
        elif absent > 0:
            message = "Absence notification: Your child has missed classes."
        else:
            message = "Your child's attendance is up to date."

        parent_html += f"""
        <div style="background:white; padding:20px;
                    margin:15px auto; max-width:450px;
                    border-radius:10px;">

            <h2>{s['name']}</h2>
            <p>Student ID: {s['student_id']}</p>
            <p>Department: {s['department']}</p>

            <p>Total Classes: {total}</p>
            <p>Classes Attended: {present}</p>
            <p>Classes Missed: {absent}</p>

            <h3>Attendance: {percentage:.2f}%</h3>

            <p>{message}</p>
        </div>
        """

    if not students:
        parent_html = "<p>No student records available.</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Parent Portal</title>
    </head>

    <body style="font-family:Arial; text-align:center;
                 padding:30px; background:#f0f4f8;">

        <h1>Parent Portal</h1>
        <h2>Child Attendance Dashboard</h2>

        {parent_html}

        <p><a href="/dashboard">Back to Dashboard</a></p>

    </body>
    </html>
    """
@app.route("/export_excel/<path:subject>")
def export_excel(subject):
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    records = connection.execute("""
        SELECT
            s.student_id,
            s.name,
            s.department,
            COUNT(DISTINCT cs.session_id) AS total,
            COALESCE(
                SUM(
                    CASE
                        WHEN ar.status = 'Present' THEN 1
                        ELSE 0
                    END
                ), 0
            ) AS present
        FROM students s
        CROSS JOIN class_sessions cs
        LEFT JOIN attendance_records ar
            ON ar.student_id = s.student_id
            AND ar.session_id = cs.session_id
        WHERE cs.subject = ?
        GROUP BY
            s.student_id, s.name, s.department
        ORDER BY s.student_id
    """, (subject,)).fetchall()

    connection.close()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance Report"

    sheet.append([
        "Student ID",
        "Student Name",
        "Department",
        "Present Classes",
        "Absent Classes",
        "Total Classes",
        "Attendance Percentage",
        "Risk Status"
    ])

    for record in records:
        total = record["total"] or 0
        present = record["present"] or 0
        absent = total - present

        percentage = (
            present / total * 100 if total > 0 else 0
        )

        if total == 0:
            risk = "No Records"
        elif percentage < 75:
            risk = "Below 75% - At Risk"
        else:
            risk = "Good"

        sheet.append([
            record["student_id"],
            record["name"],
            record["department"],
            present,
            absent,
            total,
            round(percentage, 2),
            risk
        ])

    for column in sheet.columns:
        max_length = max(
            len(str(cell.value or "")) for cell in column
        )
        sheet.column_dimensions[
            column[0].column_letter
        ].width = max_length + 3

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    safe_subject = "".join(
        c if c.isalnum() or c in " _-" else "_"
        for c in subject
    )

    return send_file(
        output,
        as_attachment=True,
        download_name=f"{safe_subject}_Attendance.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
if __name__ == "__main__":
    create_database()
    app.run(debug=True)
