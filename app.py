from flask import Flask, request, jsonify, send_from_directory
import threading

from backend_logic import (
    main,
    fetch_attendance_html,
    fetch_results,
    send_feedback
)

app = Flask(__name__, static_folder="static")

# Global lock → allows only ONE request at a time
request_lock = threading.Lock()


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


def acquire_or_busy():
    """
    Try to acquire the global lock.
    Return None if acquired, otherwise a busy response.
    """
    acquired = request_lock.acquire(blocking=False)
    if not acquired:
        return jsonify({
            "mode": "busy",
            "message": "Server is processing another request. Please wait."
        }), 429
    return None


@app.route("/student", methods=["POST"])
def api_student():
    busy = acquire_or_busy()
    if busy:
        return busy

    try:
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        regid = request.form.get("regid", "").strip()

        if not regid:
            return jsonify({"mode": "error", "message": "Missing regid"}), 400

        result = main(regid, client_ip)
        return jsonify(result)

    finally:
        request_lock.release()


@app.route("/results", methods=["POST"])
def api_results():
    busy = acquire_or_busy()
    if busy:
        return busy

    try:
        regid = request.form.get("regid")
        return jsonify({"html": fetch_results(regid)})
    finally:
        request_lock.release()


@app.route("/attendance", methods=["POST"])
def api_attendance():
    busy = acquire_or_busy()
    if busy:
        return busy

    try:
        regid = request.form.get("regid")
        semester = request.form.get("semester")
        return jsonify({
            "html": fetch_attendance_html(regid, semester)
        })
    finally:
        request_lock.release()


@app.route("/feedback", methods=["POST"])
def api_feedback():
    busy = acquire_or_busy()
    if busy:
        return busy

    try:
        data = request.get_json()
        feedback = data.get("feedback")
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        return jsonify({"response": send_feedback(feedback, client_ip)})
    finally:
        request_lock.release()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
