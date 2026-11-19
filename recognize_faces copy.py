import cv2
import os
import sqlite3

DATABASE = "attendance.db"
FACE_DIR = "faces"

DETECTOR_MODEL = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = "face_recognition_sface_2021dec.onnx"

# Create YuNet face detector
detector = cv2.FaceDetectorYN.create(
    DETECTOR_MODEL, "", (320, 320), 0.8, 0.3, 5000
)

# Create SFace recognizer
recognizer = cv2.FaceRecognizerSF.create(
    RECOGNIZER_MODEL, ""
)

# Load registered students
connection = sqlite3.connect(DATABASE)

students = connection.execute(
    "SELECT student_id, name FROM students"
).fetchall()

connection.close()

student_ids = {student[0] for student in students}

# Load registered face features
known_features = {}

for filename in os.listdir(FACE_DIR):

    if not filename.lower().endswith(".jpg"):
        continue

    student_id = filename.rsplit("_", 1)[0]

    if student_id not in student_ids:
        continue

    path = os.path.join(FACE_DIR, filename)
    image = cv2.imread(path)

    if image is None:
        continue

    height, width = image.shape[:2]
    detector.setInputSize((width, height))

    _, faces = detector.detect(image)

    if faces is None or len(faces) != 1:
        print("Could not detect one face in:", filename)
        continue

    aligned_face = recognizer.alignCrop(image, faces[0])
    feature = recognizer.feature(aligned_face)

    known_features.setdefault(student_id, []).append(feature)

if not known_features:
    print("No usable registered face images found.")
    raise SystemExit

print("Registered students loaded:", len(known_features))

# Open webcam
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Unable to open webcam.")
    raise SystemExit

print("Recognition test started.")
print("Look at the camera. Press Q to quit.")
print("Attendance recording is disabled.")

try:
    while True:

        success, frame = camera.read()

        if not success:
            print("Unable to read camera.")
            break

        height, width = frame.shape[:2]
        detector.setInputSize((width, height))

        _, faces = detector.detect(frame)

        if faces is not None:

            for face_data in faces:

                aligned_face = recognizer.alignCrop(
                    frame, face_data
                )

                current_feature = recognizer.feature(
                    aligned_face
                )

                best_score = -1
                second_best_score = -1
                best_id = None

                # Compare with every registered student
                for student_id, features in known_features.items():

                    scores = [
                        recognizer.match(
                            current_feature,
                            saved_feature,
                            cv2.FaceRecognizerSF_FR_COSINE
                        )
                        for saved_feature in features
                    ]

                    student_score = max(scores)

                    if student_score > best_score:
                        second_best_score = best_score
                        best_score = student_score
                        best_id = student_id

                    elif student_score > second_best_score:
                        second_best_score = student_score

                x, y, w, h = map(int, face_data[:4])

                if best_score < 0.363:
                    label = f"Unknown ({best_score:.2f})"
                    color = (0, 0, 255)

                elif (
                    second_best_score >= 0
                    and best_score - second_best_score < 0.05
                ):
                    label = f"Uncertain ({best_score:.2f})"
                    color = (0, 165, 255)

                else:
                    label = f"Candidate: {best_id} ({best_score:.2f})"
                    color = (0, 255, 0)

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    color,
                    2
                )

                cv2.putText(
                    frame,
                    label,
                    (x, max(25, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2
                )

        cv2.imshow("SFace Recognition Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    cv2.destroyAllWindows()

print("Recognition test stopped.")