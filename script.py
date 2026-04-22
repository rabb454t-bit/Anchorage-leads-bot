import requests
import pdfplumber
import pandas as pd
from datetime import datetime
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

PDF_URL = "https://public.courts.alaska.gov/web/scheduled/docs/crchgfiled.pdf"

FELONY_KEYWORDS = ["ASSAULT", "ROBBERY", "BURGLARY", "WEAPON", "FELONY", "DRUG", "DUI"]
HIGH_PRIORITY = ["ASSAULT", "WEAPON", "ROBBERY"]

def connect_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Anchorage Leads").sheet1

def download_pdf():
    r = requests.get(PDF_URL)
    with open("file.pdf", "wb") as f:
        f.write(r.content)

def extract_lines():
    lines = []
    with pdfplumber.open("file.pdf") as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))
    return lines

def clean_name(raw):
    match = re.findall(r"([A-Z][a-z]+,\s[A-Z][a-z]+)", raw)
    return match[0] if match else None

def classify_charge(text):
    text_upper = text.upper()
    for word in FELONY_KEYWORDS:
        if word in text_upper:
            return "Felony"
    return "Misdemeanor"

def score_priority(text):
    text_upper = text.upper()
    for word in HIGH_PRIORITY:
        if word in text_upper:
            return "HIGH"
    if any(word in text_upper for word in FELONY_KEYWORDS):
        return "MED"
    return "LOW"

def parse(lines):
    data = []
    for line in lines:
        if "Anchorage" not in line:
            continue

        name = clean_name(line)
        if not name:
            continue

        charge_type = classify_charge(line)
        priority = score_priority(line)

        data.append([
            name,
            datetime.now().strftime("%Y-%m-%d"),
            line,
            charge_type,
            priority,
            "Anchorage",
            "UNKNOWN",
            datetime.now().strftime("%Y-%m-%d"),
            ""
        ])
    return data

def upload(sheet, rows):
    existing = sheet.get_all_values()
    existing_names = set(r[0] for r in existing[1:])

    new_rows = [r for r in rows if r[0] not in existing_names]

    if new_rows:
        sheet.append_rows(new_rows)
        return len(new_rows)
    return 0

def main():
    sheet = connect_sheet()
    download_pdf()
    lines = extract_lines()
    rows = parse(lines)
    count = upload(sheet, rows)

    print(f"{count} new leads added")

if name == "__main__":
    main()
