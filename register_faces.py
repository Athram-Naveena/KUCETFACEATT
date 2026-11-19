import cv2
import sqlite3
import os

DATABASE = "attendance.db"
FACE_DIR = "faces"

os.makedirs(FACE_DIR, exist_ok=True)

connection = sqlite3.connect(DATABASE)

students = connection.execute(
    "SELECT student_id, name FROM students"
).fetchall()

connection.close()

if not students:
    print("No students registered. Register students first.")
    raise SystemExit

print("\nRegistered Students:")

for student_id, name in students:
    print(f"{student_id} - {name}")

student_id = input("\nEnter the student ID to register their face: ").strip()

student = next(
    (s for s in students if s[0] == student_id),
    None
)

if student is None:
    print("Student ID not found.")
    raise SystemExit

safe_id = "".join(
    c for c in student_id if c.isalnum() or c in "-_"
)

if not safe_id:
    print("Invalid student ID.")
    raise SystemExit

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Unable to open webcam.")
    raise SystemExit

face_detector = cv2.CascadeClassifier(
    "haarcascade_frontalface_default.xml"
)

if face_detector.empty():
    print("Face detection file could not be loaded.")
    camera.release()
    raise SystemExit
    

count = 0

print("\nLook at the camera.")
print("Press C to capture a face image.")
print("Press Q to quit.")

while True:
    success, frame = camera.read()

    if not success:
        print("Unable to capture camera frame.")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
    )

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.putText(
        frame, f"Saved: {count}", (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
    )

    cv2.imshow("Student Face Registration", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    if key == ord("c"):
        if len(faces) != 1:
            print("Ensure exactly one face is visible, then press C.")
            continue

        x, y, w, h = faces[0]
        face_image = frame[y:y+h, x:x+w]

        filename = os.path.join(
            FACE_DIR, f"{safe_id}_{count + 1}.jpg"
        )

        if cv2.imwrite(filename, face_image):
            count += 1
            print(f"Saved face image {count}: {filename}")

camera.release()
cv2.destroyAllWindows()

print(f"\nRegistration session ended. Images captured: {count}")
print("Repeat for each student using their own consented face images.")