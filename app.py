from flask import Flask, request, jsonify, send_from_directory
from swrn_attendance import fetch_attendance_html
from swrn_attendance_details import extract_details

app = Flask(__name__, static_folder="static")


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


@app.route("/student", methods=["POST"])
def student():
    regid = request.form.get("regid", "").strip()
    if not regid:
        return jsonify({"error": "Missing regid"}), 400

    details = extract_details(regid)
    if not details:
        return jsonify({"error": "Student not found"}), 404

    semester = "Fourth Semester"
    attendance_html = fetch_attendance_html(regid, semester)

    return jsonify({
        "details": details,
        "attendance": attendance_html
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
