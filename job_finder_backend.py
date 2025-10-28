import re
import smtplib
import PyPDF2
import pandas as pd
from io import BytesIO
from email.message import EmailMessage
from rapidfuzz import fuzz
from googleapiclient.discovery import build
import streamlit as st

def extract_resume_text(resume_file):
    reader = PyPDF2.PdfReader(resume_file)
    return "".join([page.extract_text() or "" for page in reader.pages]).lower()

def extract_skills(resume_text):
    skill_list = [
        "python", "java", "c++", "sql", "linux", "cloud", "aws", "azure", "gcp",
        "docker", "kubernetes", "networking", "security", "machine learning",
        "data analysis", "pl/sql", "troubleshooting", "automation",
        "shell scripting", "monitoring", "integration", "etl", "data warehouse"
    ]
    return [s for s in skill_list if s in resume_text]

def extract_experience(resume_text):
    year_matches = re.findall(r"(\d+)\s*(year|years|month|months)", resume_text)
    total_months = sum(int(num) * (12 if "year" in unit else 1) for num, unit in year_matches)
    return f"{round(total_months/12, 1)} years" if total_months > 0 else "Not specified"

def search_jobs(skills, filters):
    api_key = st.secrets["google_api"]["api_key"]
    cx_id = st.secrets["google_api"]["cx_id"]
    service = build("customsearch", "v1", developerKey=api_key)

    query = " ".join(skills)
    if filters["company"]:
        query += f" site:{filters['company'].lower()}.com"
    else:
        query += " (site:linkedin.com/jobs OR site:google.com/about/careers OR site:amazon.jobs OR site:microsoft.com/en-us/careers)"
    
    if filters["location"]:
        query += f" {filters['location']}"
    if filters["keywords"]:
        query += f" {filters['keywords']}"
    if filters["work_type"] != "Any":
        query += f" {filters['work_type']}"

    results = []
    for start in range(1, 15, 7):
        res = service.cse().list(q=query, cx=cx_id, start=start, sort="date:d:s").execute()
        if "items" in res:
            results.extend(res["items"])
    return results

def match_jobs(skills, job_results):
    matched = []
    for job in job_results:
        title = job.get("title", "").lower()
        snippet = job.get("snippet", "").lower()
        text = f"{title} {snippet}"
        score = sum(fuzz.partial_ratio(skill, text) for skill in skills) / len(skills)
        if score > 50:
            matched.append({
                "title": job.get("title", "N/A"),
                "link": job.get("link", ""),
                "score": round(score, 2),
                "snippet": job.get("snippet", "")
            })
    return pd.DataFrame(matched).sort_values(by="score", ascending=False)

def send_email_with_jobs(matched_jobs, recipient_email):
    if not recipient_email:
        return  # skip if user didn’t enter email

    sender = st.secrets["email"]["sender_email"]
    password = st.secrets["email"]["app_password"]

    msg = EmailMessage()
    msg["Subject"] = "Your Smart Job Matches"
    msg["From"] = sender
    msg["To"] = recipient_email

    top5 = matched_jobs.head(5)
    body = "Here are your top 5 job matches:\n\n" + "\n\n".join(
        [f"{i+1}. {r['title']} - {r['link']}" for i, r in top5.iterrows()]
    )
    msg.set_content(body)

    csv_data = BytesIO()
    matched_jobs.to_csv(csv_data, index=False)
    csv_data.seek(0)
    msg.add_attachment(csv_data.read(), maintype="text", subtype="csv", filename="matched_jobs.csv")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

def process_resume_and_jobs(resume_file, filters, recipient_email):
    resume_text = extract_resume_text(resume_file)
    skills = extract_skills(resume_text)
    exp = extract_experience(resume_text)
    job_results = search_jobs(skills, filters)
    matched_jobs = match_jobs(skills, job_results)

    send_email_with_jobs(matched_jobs, recipient_email)
    return matched_jobs, skills, exp
