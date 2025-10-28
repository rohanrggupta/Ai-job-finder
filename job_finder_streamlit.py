import os
import re
import csv
import smtplib
import PyPDF2
import pandas as pd
from io import StringIO
from email.message import EmailMessage
from rapidfuzz import fuzz
from googleapiclient.discovery import build
import streamlit as st
from datetime import datetime, timedelta

# ============ PAGE SETUP ============ #
st.set_page_config(page_title="AI Job Finder", layout="wide", page_icon="🧠")
st.title("🤖 Smart Job Finder")
st.caption("Upload your resume and instantly find matching job postings across top product-based companies!")

# ============ SECRET VALIDATION ============ #
required_secrets = ["google_api_key", "google_cx_id"]
optional_secrets = ["email_user", "app_password"]

missing_secrets = [key for key in required_secrets if key not in st.secrets]
if missing_secrets:
    st.error(f"🚨 Missing required secrets in `.streamlit/secrets.toml`: {', '.join(missing_secrets)}")
    st.stop()

def get_secret(key, default=None):
    return st.secrets[key] if key in st.secrets else default

api_key = get_secret("google_api_key")
cx_id = get_secret("google_cx_id")
email_user = get_secret("email_user")
app_password = get_secret("app_password")

# ============ RESUME FUNCTIONS ============ #
def extract_resume_text(uploaded_file):
    text = ""
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.lower()

def extract_skills(resume_text):
    skill_list = [
        "python", "java", "c++", "sql", "linux", "cloud", "aws", "azure", "gcp",
        "docker", "kubernetes", "networking", "security", "machine learning",
        "data analysis", "pl/sql", "troubleshooting", "automation", "shell scripting",
        "monitoring", "integration", "etl", "data warehouse", "big data"
    ]
    return [s for s in skill_list if s in resume_text]

def extract_experience(resume_text):
    year_matches = re.findall(r"(\d+)\s*(year|years|yr|yrs|month|months)", resume_text)
    total_months = 0
    for num, unit in year_matches:
        num = int(num)
        total_months += num * 12 if "year" in unit else num
    return round(total_months / 12, 1)

# ============ JOB SEARCH ============ #
def search_jobs(skills, location_filter="", keyword_filter="", company_filter=""):
    service = build("customsearch", "v1", developerKey=api_key)
    
    query = " ".join(skills) + " site:(linkedin.com/jobs OR google.com/about/careers OR amazon.jobs OR microsoft.com/en-us/careers OR apple.com/careers OR meta.com/careers)"
    
    if location_filter:
        query += f" {location_filter}"
    if keyword_filter:
        query += f" {keyword_filter}"
    if company_filter:
        query += f" {company_filter}"

    results = []
    for start in range(1, 15, 7):
        res = service.cse().list(q=query, cx=cx_id, start=start, sort="date:d:s").execute()
        if "items" in res:
            results.extend(res["items"])
    return results

# ============ DATE & JOB FILTER ============ #
def filter_recent_jobs(job_results, max_days):
    filtered = []
    for job in job_results:
        snippet = job.get("snippet", "").lower()
        match = re.search(r"(\d+)\s*(day|days|week|weeks)", snippet)
        if match:
            num, unit = int(match.group(1)), match.group(2)
            days = num * 7 if "week" in unit else num
            if days <= max_days:
                filtered.append(job)
        else:
            filtered.append(job)  # keep if no date info (assume recent)
    return filtered

# ============ JOB MATCHING ============ #
def match_jobs(skills, jobs):
    matched = []
    for job in jobs:
        title = job.get("title", "").lower()
        snippet = job.get("snippet", "").lower()
        job_text = f"{title} {snippet}"
        score = sum(fuzz.partial_ratio(skill, job_text) for skill in skills) / len(skills) if skills else 0
        if score > 50:
            matched.append({
                "title": job.get("title", "N/A"),
                "link": job.get("link", "N/A"),
                "snippet": job.get("snippet", "N/A"),
                "score": round(score, 2)
            })
    return sorted(matched, key=lambda x: x["score"], reverse=True)

# ============ EMAIL ALERT ============ #
def send_email(to_email, matched_jobs):
    if not email_user or not app_password:
        st.warning("⚠️ Email credentials not found in secrets.toml. Skipping email alert.")
        return

    top5 = matched_jobs[:5]
    body = "\n\n".join([f"{j['title']} ({j['score']}%)\n{j['link']}" for j in top5])

    msg = EmailMessage()
    msg["Subject"] = "🎯 Top Job Matches for You!"
    msg["From"] = email_user
    msg["To"] = to_email
    msg.set_content(f"Here are your top 5 matched jobs:\n\n{body}")

    # Attach full list as CSV
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["title", "link", "score", "snippet"])
    writer.writeheader()
    writer.writerows(matched_jobs)
    msg.add_attachment(csv_buffer.getvalue(), filename="matched_jobs.csv")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_user, app_password)
        smtp.send_message(msg)
    st.success(f"📧 Email sent successfully to {to_email}!")

# ============ SIDEBAR FILTERS ============ #
st.sidebar.header("🔍 Job Filters")
location = st.sidebar.text_input("🌍 Location (e.g., India, Remote):")
keywords = st.sidebar.text_input("🧠 Keywords (e.g., intern, cloud, devops):")
company = st.sidebar.text_input("🏢 Company (e.g., Google, Amazon):")
days_filter = st.sidebar.slider("🕓 Jobs posted within (days):", 1, 30, 10)
user_email = st.sidebar.text_input("📩 Your email (to receive results):")

# Submit button for filters
apply_filters = st.sidebar.button("✅ Apply Filters")

# ============ FILE UPLOAD ============ #
uploaded_file = st.file_uploader("📂 Upload your resume (PDF only):", type=["pdf"])

if uploaded_file and apply_filters:
    st.info("🔍 Analyzing your resume...")
    text = extract_resume_text(uploaded_file)
    skills = extract_skills(text)
    exp = extract_experience(text)

    st.success(f"✅ Found {len(skills)} skills: {', '.join(skills)}")
    st.write(f"🧩 Estimated Experience: {exp} years")

    st.write("🌐 Fetching job postings...")
    jobs = search_jobs(skills, location, keywords, company)
    recent_jobs = filter_recent_jobs(jobs, days_filter)
    matched_jobs = match_jobs(skills, recent_jobs)

    if matched_jobs:
        st.success("✨ Showing results after the applied filter ✨")
        st.write(f"🎯 Found {len(matched_jobs)} matching jobs!")
        df = pd.DataFrame(matched_jobs)
        st.dataframe(df[["title", "link", "score"]])

        # Download Button
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download job list as CSV", data=csv_data, file_name="matched_jobs.csv", mime="text/csv")

        # Email Alert
        if user_email:
            send_email(user_email, matched_jobs)
    else:
        st.warning("❌ No matching jobs found. Try adjusting filters or uploading another resume.")

elif uploaded_file and not apply_filters:
    st.info("ℹ️ Click '✅ Apply Filters' in the sidebar to start searching with your selected filters.")