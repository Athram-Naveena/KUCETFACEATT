from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Student Attendance System</title>
        <style>
            body {
                font-family: Arial;
                text-align: center;
                background: #f0f4f8;
                padding: 40px;
            }
            h1 {
                color: #123456;
            }
            .box {
                background: white;
                padding: 25px;
                margin: 20px auto;
                max-width: 500px;
                border-radius: 10px;
            }
            button {
                padding: 12px 20px;
                margin: 8px;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <h1>Student Attendance System</h1>

        <div class="box">
            <h2>Attendance Dashboard</h2>
            <p>Facial Recognition Attendance</p>
            <button onclick="alert('Face recognition will be added next!')">
                Mark Attendance
            </button>
            <button onclick="alert('Attendance records will be added next!')">
                View Attendance
            </button>
            <p>Attendance Risk Analysis</p>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)