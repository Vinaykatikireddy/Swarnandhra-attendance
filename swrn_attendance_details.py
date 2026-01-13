import requests
from bs4 import BeautifulSoup

DETAILS_URL = "https://www.swarnandhra.ac.in/campusattendance/hostel/search_students.php"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def extract_details(reg_no: str):
    response = requests.post(
        DETAILS_URL,
        data={"search": reg_no},
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    card = soup.find("div", class_="student-card")
    if not card:
        return None

    details = {}

    details["name"] = card.find("div", class_="card-name").get_text(strip=True)
    details["regid"] = card.find("div", class_="card-reg-id").get_text(strip=True)

    for row in card.find_all("div", class_="card-info-row"):
        label = row.find("span", class_="card-label").get_text(strip=True).replace(":", "")
        value = row.find("span", class_="card-value").get_text(strip=True)
        details[label.lower()] = value

    return details
