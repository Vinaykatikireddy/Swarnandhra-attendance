import requests
from bs4 import BeautifulSoup

URL = "https://www.swarnandhra.ac.in/campusattendance/hostel/view_attendance.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_attendance_html(regid, semester):
    payload = {
        "regid": regid,
        "semester": semester
    }

    response = requests.post(
        URL,
        data=payload,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")

    if not tables:
        return "<div>No attendance data found</div>"

    # Return only tables (safe HTML)
    return "".join(str(table) for table in tables)
