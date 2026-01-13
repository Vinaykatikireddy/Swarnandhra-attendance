from flask import Flask, request, Response, send_from_directory
from swrn_attendance import fetch_attendance_html

app = Flask(__name__, static_folder="static")


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


@app.route("/attendance", methods=["POST"])
def attendance():
    regid = request.form.get("regid", "").strip()
    semester = request.form.get("semester", "").strip()

    if not regid or not semester:
        return "Missing parameters", 400

    html = fetch_attendance_html(regid, semester)
    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
