from backend_logic import main, fetch_attendance_html, fetch_results, send_feedback
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/student", methods=["POST"])
def api_student():
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    regid = request.form.get("regid", "").strip()
    if not regid:
        return jsonify({"error": "Missing regid"}), 400
    return jsonify(main(regid, client_ip))

@app.route("/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json()
    feedback = data.get("feedback")
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return jsonify({"response": send_feedback(feedback, client_ip)})


@app.route("/results", methods=["POST"])
def api_results():
    regid = request.form.get("regid")
    return jsonify({"html": fetch_results(regid)})

@app.route("/attendance", methods=["POST"])
def api_attendance():
    regid = request.form.get("regid")
    return jsonify({"html": fetch_attendance_html(regid, "Fourth Semester")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
