from backend_logic import main, fetch_attendance_html
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/student", methods=["POST"])
def api_student():
    regid = request.form.get("regid", "").strip()
    if not regid:
        return jsonify({"error": "Missing regid"}), 400
    return jsonify(main(regid))


@app.route("/attendance", methods=["POST"])
def api_attendance():
    regid = request.form.get("regid")
    return jsonify({"html": fetch_attendance_html(regid, "Fourth Semester")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
