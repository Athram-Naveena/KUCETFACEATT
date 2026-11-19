import cv2
import os
import sqlite3
import numpy as np
from datetime import datetime

DATABASE = "attendance.db"
FACE_DIR = "faces"
connection = sqlite3.connect(DATABASE)

connection.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        attendance_date TEXT NOT NULL,
        attendance_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Present',
        UNIQUE(student_id, attendance_date)
    )
""")

connection.commit()
connection.close()
detector = cv2.CascadeClassifier(
    "haarcascade_frontalface_default.xml"
)

if detector.empty():
    print("Face detection file not found.")
    raise SystemExit

known_faces = []
known_ids = []

for filename in os.listdir(FACE_DIR):
    if filename.lower().endswith(".jpg"):
        path = os.path.join(FACE_DIR, filename)
        image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        if image is not None:
            image = cv2.resize(image, (100, 100))
            known_faces.append(image)
            known_ids.append(filename.rsplit("_", 1)[0])

if not known_faces:
    print("No registered face images found.")
    raise SystemExit

print("Registered face images loaded:", len(known_faces))

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Unable to open webcam.")
    raise SystemExit

marked_today = set()

print("Look at the camera. Press Q to quit.")

try:
    while True:
        success, frame = camera.read()

        if not success:
            print("Unable to read camera.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = detector.detectMultiScale(
            gray, scaleFactor=1.1,
            minNeighbors=5, minSize=(100, 100)
        )

        for (x, y, w, h) in faces:
            current_face = cv2.resize(
                gray[y:y+h, x:x+w], (100, 100)
            )

            best_score = float("inf")
            best_id = None

            for saved_face, student_id in zip(known_faces, known_ids):
                score = np.mean(
                    (current_face.astype(float)
                     - saved_face.astype(float)) ** 2
                )

                if score < best_score:
                    best_score = score
                    best_id = student_id

            # Experimental pixel matching; not reliable enough
            # for real attendance decisions.
            if best_score < 2500:
                label = "Possible match: " + best_id
                color = (0, 255, 0)

                if best_id not in marked_today:
                    connection = sqlite3.connect(DATABASE)

                    student = connection.execute(
                        "SELECT name FROM students WHERE student_id = ?",
                        (best_id,)
                    ).fetchone()

                    if student:
                        now = datetime.now()
                        date_today = now.strftime("%Y-%m-%d")
                        time_now = now.strftime("%H:%M:%S")

                        try:
                            connection.execute(
                                """INSERT INTO attendance
                                (student_id, attendance_date, attendance_time, status)
                                VALUES (?, ?, ?, 'Present')""",
                                (best_id, date_today, time_now)
                            )
                            connection.commit()
                            marked_today.add(best_id)

                            print(
                                f"Attendance recorded for {student[0]} "
                                f"({best_id}) at {time_now}"
                            )

                        except sqlite3.IntegrityError:
                            marked_today.add(best_id)
                            print("Attendance already recorded today.")

                    connection.close()
            else:
                label = "Unknown face"
                color = (0, 0, 255)

            cv2.rectangle(
                frame, (x, y), (x+w, y+h), color, 2
            )
            cv2.putText(
                frame, label, (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
            )

        cv2.imshow("Student Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    cv2.destroyAllWindows()

print("Face recognition stopped.")