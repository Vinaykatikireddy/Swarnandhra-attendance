import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

SWARNANDHRA_URL = "https://www.swarnandhra.ac.in/campusattendance/hostel/search_students.php"
INDIARESULTS_URL = "https://ap-inter-2nd-year-result.indiaresults.com/ap/bieap/intermediate-2-year-gen-exam-result-2024/name-results.aspx"
BET_E_PORTAL = "https://www.swarnandhraexambranch.com/"

HEADERS = {"User-Agent": "Mozilla/5.0"}

session = requests.Session()
session.headers.update(HEADERS)

# New: shared session + defaults + simple TTL cache
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
DEFAULT_TIMEOUT = 10
_CACHE = {}  # regno -> (timestamp, payload)
CACHE_TTL = 600  # seconds

def extract_student_details(reg_no: str):
    response = requests.post(SWARNANDHRA_URL, data={"search": reg_no}, timeout=DEFAULT_TIMEOUT)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    card = soup.find("div", class_="student-card")
    if not card:
        return None

    regid = card.find("div", class_="card-reg-id").get_text(strip=True)
    name = card.find("div", class_="card-name").get_text(strip=True)

    info_rows = card.find_all("div", class_="card-info-row")
    details = {"Name": name, "regid": regid}

    for row in info_rows:
        label = row.find("span", class_="card-label").get_text(strip=True).replace(":", "")
        value = row.find("span", class_="card-value").get_text(strip=True)
        details[label] = value

    return details

def asp_hidden(session, url):
    r = session.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    return {tag["name"]: tag.get("value","") for tag in soup.find_all("input") if tag.get("name") in ["__VIEWSTATE","__EVENTVALIDATION","__VIEWSTATEGENERATOR"]}


def fetch_payment_id(session, hall_ticket, mobile_no, dob):
    url = "https://cets.apsche.ap.gov.in/EAPCET24/Eapcet/EAPCET_PaymentStatus.aspx"
    h = asp_hidden(session, url)
    payload = {
        "__VIEWSTATE": h.get("__VIEWSTATE",""),
        "__EVENTVALIDATION": h.get("__EVENTVALIDATION",""),
        "__VIEWSTATEGENERATOR": h.get("__VIEWSTATEGENERATOR",""),
        "ctl00$EapcetpageContent$txtQualifyingExaminationHallticketNo": hall_ticket,
        "ctl00$EapcetpageContent$txtMobileNumber": mobile_no,
        "ctl00$EapcetpageContent$txtDOB": dob,
        "ctl00$EapcetpageContent$rbtStream": "1",
        "ctl00$EapcetpageContent$btnCheckPaymentStatus": "Check Payment Status"
    }

    r = session.post(url, data=payload, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    span = soup.find("span", id=lambda x: x and "lblPaymentRefID" in x)
    return span.text.strip() if span else None


def search_hallticket(session, name):
    r = session.post(INDIARESULTS_URL, data={"name": name}, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", id="GridView1")
    if not table:
        return None

    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = [c.text.strip() for c in row.find_all("td")]
        if len(cols) >= 3 and cols[1].upper() == name.upper():
            return cols[2]
    return None

def extract_hidden(html):
    soup = BeautifulSoup(html, "html.parser")
    return {
        tag["name"]: tag.get("value", "")
        for tag in soup.find_all("input")
        if tag.get("name") in (
            "__VIEWSTATE",
            "__EVENTVALIDATION",
            "__VIEWSTATEGENERATOR",
        )
    }

def login_student(session, regd):
    login_url = BET_E_PORTAL + "/Login.aspx"

    # Step 1: initial load
    r = session.get(login_url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    h = extract_hidden(r.text)

    # Step 2: click Student Login (critical)
    payload = {
        **h,
        "__EVENTTARGET": "lnkStudent",
        "__EVENTARGUMENT": "",
    }
    r = session.post(login_url, data=payload, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    h = extract_hidden(r.text)

    # Step 3: submit credentials (same page state)
    payload = {
        **h,
        "txtUserId": regd,
        "txtPwd": regd,
        "btnLogin": "Login",
    }
    session.post(login_url, data=payload, headers=HEADERS, allow_redirects=True, timeout=DEFAULT_TIMEOUT)

    # Auth verification
    if ".ASPXAUTH" not in session.cookies.get_dict():
        raise RuntimeError("Login failed (ASPXAUTH missing)")


def extract_dob_college_img(regd):
    login_student(session, regd)

    # Main student page
    main_url = BET_E_PORTAL + "/StudentLogin/MainStud.aspx"
    r = session.get(main_url, timeout=DEFAULT_TIMEOUT)
    h = extract_hidden(r.text)

    # Click Overall Marks
    payload = {
        **h,
        "__EVENTTARGET": "ctl00$lnkStuInfo",
        "__EVENTARGUMENT": "",
    }
    session.post(main_url, data=payload, allow_redirects=True, timeout=DEFAULT_TIMEOUT)

    info_url = BET_E_PORTAL + "/StudentLogin/Student/StudentInformation.aspx"
    r = session.get(info_url, timeout=DEFAULT_TIMEOUT)

    if "BET e-Portal Login" in r.text:
        raise RuntimeError("Session lost after login")

    soup = BeautifulSoup(r.text, "html.parser")

    #extract college image
    college_img_tag = soup.find(id="ctl00_ImgStudent")
    college_image = None
    if college_img_tag:
        college_img_url = college_img_tag.get("src")
        final_img_url = urljoin(BET_E_PORTAL + "/StudentLogin/Student/", college_img_url)
        college_img = session.get(final_img_url, timeout=DEFAULT_TIMEOUT)
        img_data = college_img.content
        # make sure we don't try to slice badly; encode whole content
        college_image = base64.b64encode(img_data).decode("utf-8")
        college_image = "data:image/jpeg;base64," + college_image

    #extract date of birth
    panel = soup.select_one("#ctl00_cpStudCorner_txtDOB")
    if not panel:
        raise RuntimeError("Date of birth not found")

    dob = panel.get('value', '')
    return dob, college_image

def fetch_attendance_html(regid, semester):
    url = "https://www.swarnandhra.ac.in/campusattendance/hostel/view_attendance.php"
    response = requests.post(url, data={"regid": regid, "semester": semester}, timeout=DEFAULT_TIMEOUT)
    if response.status_code != 200:
        return None
    # return decoded HTML (was str(response.content) before)
    return response.text

def extract_personal_info_from_html(html, dob, inter_hall_ticket):
    soup = BeautifulSoup(html, "html.parser")
    
    tag = soup.find(id="lblAadharCardNo")
    aadhaar = tag.get_text(" ", strip=True) if tag else "Not Found"

    files = {}

    photo = soup.find(id="imgPhoto")
    if photo:
        img_data = photo.get("src")
        files["photo_base64"] = img_data


    dob_fmt = __import__("datetime").datetime.strptime(dob, "%d/%m/%Y").strftime("%Y-%m-%d")
    memo = requests.get(
        f"https://bieapi.apcfss.in/apbie/header-services/getShortMemo/2024/March/1/{inter_hall_ticket}/{dob_fmt}/2",
        timeout=DEFAULT_TIMEOUT
    )
    if memo.status_code == 200:
        pdf_base64 = base64.b64encode(memo.content).decode("utf-8")
        files["inter_memo"] = pdf_base64

    return aadhaar, files

def fetch_application_html(session, pid, regno, hall_ticket, mobile_no, dob):
    url = "https://cets.apsche.ap.gov.in/EAPCET24/Eapcet/EAPCET_GetPrintApplication.aspx"
    h = asp_hidden(session, url)

    payload = {
        "__VIEWSTATE": h["__VIEWSTATE"],
        "__EVENTVALIDATION": h["__EVENTVALIDATION"],                                                              "__VIEWSTATEGENERATOR": h["__VIEWSTATEGENERATOR"],
        "ctl00$EapcetpageContent$txtPaymentId": pid,
        "ctl00$EapcetpageContent$txtApplicationNumber": regno,
        "ctl00$EapcetpageContent$txtQualifyingExaminationHallticketNum": hall_ticket,
        "ctl00$EapcetpageContent$txtReferenceMobileNumber": mobile_no,
        "ctl00$EapcetpageContent$txtReferenceDOB": dob,
        "ctl00$EapcetpageContent$btnVerification": "Get Application Details"
    }

    r = session.post(url, data=payload, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    a = soup.find("a")
    if a:
        return session.get(urljoin(url, a["href"]), headers=HEADERS).text
    return r.text


def fetch_regno(session, pid, hall_ticket, mobile_no, dob):
    url = "https://cets.apsche.ap.gov.in/EAPCET24/Eapcet/EAPCET_ApplicationStatus.aspx"
    h = asp_hidden(session, url)

    payload = {
        "__VIEWSTATE": h["__VIEWSTATE"],
        "__EVENTVALIDATION": h["__EVENTVALIDATION"],
        "__VIEWSTATEGENERATOR": h["__VIEWSTATEGENERATOR"],
        "ctl00$EapcetpageContent$txtPaymentId": pid,
        "ctl00$EapcetpageContent$txtQualifyingExaminationHallticketNum": hall_ticket,
        "ctl00$EapcetpageContent$txtReferenceMobileNumber": mobile_no,
        "ctl00$EapcetpageContent$txtReferenceDOB": dob,
        "ctl00$EapcetpageContent$btnRegistrationStatus": "Submit"
    }

    r = session.post(url, data=payload, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")      
    span = soup.find("span", id=lambda x: x and "lblRegistration" in x)
    if not span:
        return None
    b = span.find("b")
    return b.text.strip() if b else None


"""def fetch_results(regd):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    login_student(session, regd)

    # Main student page
    main_url = BASE + "/StudentLogin/MainStud.aspx"
    r = session.get(main_url)
    h = extract_hidden(r.text)

    # Click Overall Marks
    payload = {
        **h,
        "__EVENTTARGET": "ctl00$lnkOverallMarks",
        "__EVENTARGUMENT": "",
    }
    session.post(main_url, data=payload, allow_redirects=True)
"""
def fetch_results(regd):
    # Final marks page
    final_url = BET_E_PORTAL + "/StudentLogin/Student/overallMarks.aspx"
    r = session.get(final_url)

    if "BET e-Portal Login" in r.text:
        raise RuntimeError("Session lost after login")

    soup = BeautifulSoup(r.text, "html.parser")

    panel = soup.select_one("#ctl00_cpStudCorner_PanelDueSubjects")
    if not panel:
        raise RuntimeError("Marks panel not found")

    table = panel.select_one("table.formTableAuto")
    if not table:
        raise RuntimeError("Marks table not found")

    # Remove Print button row
    export = table.select_one("#ctl00_cpStudCorner_btnExportToPDF")
    if export:
        export.find_parent("tr").decompose()

    # Insert heading
    inner = table.select_one("td > table") or table
    tbody = inner.tbody or inner

    first_row = tbody.find("tr")
    col_count = len(first_row.find_all(["td", "th"])) if first_row else 1

    tr = soup.new_tag("tr")
    th = soup.new_tag("th", colspan=str(col_count))
    th.string = regd
    th["style"] = "font-size:20px;text-align:center;"
    tr.append(th)
    tbody.insert(0, tr)

    # Minimal output HTML (fast render)
    html = f"""<!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <title>{regd}</title>
        </head>
        <body>
            {table}
        </body>
    </html>
    """
    return html

def main(college_reg_no, client_ip):
    APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzaYehzbxVn1p_-XOG3INMPZpKQCE7NPo_vaZJ8zuiQO5-g0ZZHkM8JlePTJxyrzRQZ/exec"
    payload = { "regid": college_reg_no, "ip": client_ip }
    headers = { "Content-Type": "application/json" }
    try:
        requests.post(APPS_SCRIPT_URL, json=payload, headers=headers, timeout=3)
    except requests.RequestException:
        pass

    # simple TTL cache check
    now = time.time()
    cached = _CACHE.get(college_reg_no)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]

    dob, college_image = extract_dob_college_img(college_reg_no)
    student = extract_student_details(college_reg_no)

    student["college_image"]=college_image

    if not student:
        result = {"mode": "error", "message": "Invalid reg no"}
        _CACHE[college_reg_no] = (now, result)
        return result

    with requests.Session() as s:
        hall_ticket = search_hallticket(s, student["Name"][:30])
        if not hall_ticket:
            result = {"mode": "basic", "student": student}
            _CACHE[college_reg_no] = (now, result)
            return result

        for mobile in [student.get("Mobile"), student.get("Father Mobile")]:
            if not mobile:
                continue
            pid = fetch_payment_id(s, hall_ticket, mobile, dob)
            if pid:
                break
        else:
            result = {"mode": "basic", "student": student}
            _CACHE[college_reg_no] = (now, result)
            return result

        regno = fetch_regno(s, pid, hall_ticket, mobile, dob)
        if not regno:
            result = {"mode": "basic", "student": student}
            _CACHE[college_reg_no] = (now, result)
            return result

        html = fetch_application_html(s, pid, regno, hall_ticket, mobile, dob)
        aadhaar_no, files = extract_personal_info_from_html(html, dob, hall_ticket)

        student["Aadhaar"]=aadhaar_no
        student["Eapcet_application"]=html
        
        result = {
            "mode": "full",
            "student": student,
            "files": files
        }
        _CACHE[college_reg_no] = (now, result)
        return result
