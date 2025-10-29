import re
import smtplib
import PyPDF2
import pandas as pd
from io import BytesIO
from email.message import EmailMessage
from rapidfuzz import fuzz
from googleapiclient.discovery import build
import streamlit as st
import json
import time

# ==============================
# Resume Extraction
# ==============================
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

# ==============================
# Normal Job Search (Google API)
# ==============================
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
    query += " jobs"

    results = []
    for start in range(1, 15, 7):
        res = service.cse().list(q=query, cx=cx_id, start=start, sort="date:d:s").execute()
        if "items" in res:
            results.extend(res["items"])
    return results

# ==============================
# Job Matching
# ==============================
def match_jobs(skills, job_results, posted_within_days):
    matched = []
    for job in job_results:
        title = job.get("title", "").lower()
        snippet = job.get("snippet", "").lower()
        text = f"{title} {snippet}"

        if not skills:
            continue
        score = sum(fuzz.partial_ratio(skill, text) for skill in skills) / len(skills)

        days_match = re.search(r"(\d+)\s*day", snippet)
        days_ago = int(days_match.group(1)) if days_match else None

        if days_ago is not None and days_ago > posted_within_days:
            continue

        if score > 50:
            matched.append({
                "title": job.get("title", "N/A"),
                "link": job.get("link", ""),
                "score": round(score, 2),
                "snippet": job.get("snippet", ""),
                "posted_days_ago": days_ago if days_ago else "Unknown"
            })

    if not matched:
        return pd.DataFrame()
    return pd.DataFrame(matched).sort_values(by="score", ascending=False)

# ==============================
# AI Summaries for Matches
# ==============================
def add_ai_summaries(matched_jobs, skills):
    if matched_jobs.empty:
        return matched_jobs

    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["google_ai"]["google_api_key"])
        model = genai.GenerativeModel("gemini-2.0-flash")

        summaries = []
        for _, row in matched_jobs.iterrows():
            prompt = f"""
            Candidate skills: {', '.join(skills)}.
            Job title: {row['title']}
            Job details: {row['snippet']}
            Write one short, clear sentence summarizing why this job fits the candidate's profile.
            """
            try:
                resp = model.generate_content(prompt)
                # Handle different SDK versions
                if hasattr(resp, "text"):
                    summaries.append(resp.text.strip())
                elif hasattr(resp, "candidates"):
                    text = resp.candidates[0].content.parts[0].text
                    summaries.append(text.strip())
                else:
                    summaries.append("No summary available.")
            except Exception:
                summaries.append("No summary available.")
        matched_jobs["summary"] = summaries

    except Exception as e:
        st.warning(f"⚠️ AI summaries unavailable: {e}")
        matched_jobs["summary"] = "No summary available."
    return matched_jobs

# ==============================
# Gemini-only AI Job Search
# ==============================
def ai_web_search(skills, keywords, company, location, posted_within_days):
    import google.generativeai as genai
    genai.configure(api_key=st.secrets["google_ai"]["google_api_key"])
    model = genai.GenerativeModel("gemini-2.0-flash")

    query = f"""
    You are a professional job finder.
    Return a JSON array of jobs relevant to:
    Skills: {', '.join(skills)}
    Keywords: {keywords}
    Company: {company if company else 'Any'}
    Location: {location if location else 'Remote or any'}
    Only include jobs posted within last {posted_within_days} days.

    Example:
    [
      {{
        "title": "Python Developer",
        "company": "Google",
        "location": "Bangalore, India",
        "description": "Develop scalable backend systems using Python and GCP.",
        "apply_link": "https://careers.google.com",
        "posted_days_ago": 5
      }}
    ]
    """

    try:
        response = model.generate_content(query)
        # Extract text robustly
        text = getattr(response, "text", None)
        if not text and hasattr(response, "candidates"):
            text = response.candidates[0].content.parts[0].text
        if not text:
            return pd.DataFrame(), "❌ Gemini returned no usable text."

        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return pd.DataFrame(), "❌ Couldn't parse AI results."

        job_data = json.loads(json_match.group(0))
        df = pd.DataFrame(job_data)
        for col in ["title", "company", "location", "description", "apply_link", "posted_days_ago"]:
            if col not in df.columns:
                df[col] = ""
        df["summary"] = [
            f"This {r['title']} role at {r['company']} fits your skills ({', '.join(skills)})."
            for _, r in df.iterrows()
        ]
        return df, "✅ Gemini AI job listings generated successfully."
    except Exception as e:
        return pd.DataFrame(), f"❌ Gemini AI Search failed: {e}"

# ==============================
# Email Sending
# ==============================
def send_email_with_jobs(matched_jobs, recipient_email):
    if not recipient_email:
        st.warning("Please enter a recipient email before sending results.")
        return

    try:
        sender = st.secrets["email"]["sender_email"]
        password = st.secrets["email"]["app_password"]
    except KeyError:
        st.warning("Email credentials not found in secrets.toml.")
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Smart Job Matches"
    msg["From"] = sender
    msg["To"] = recipient_email

    body = "Here are your top 5 job matches:\n\n" + "\n\n".join(
        [f"{i+1}. {r['title']} - {r.get('link', r.get('apply_link', ''))}" for i, r in matched_jobs.head(5).iterrows()]
    )
    msg.set_content(body)

    csv_data = BytesIO()
    matched_jobs.to_csv(csv_data, index=False)
    csv_data.seek(0)
    msg.add_attachment(csv_data.read(), maintype="text", subtype="csv", filename="matched_jobs.csv")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
    st.success(f"✅ Email sent successfully to {recipient_email}")

# ==============================
# Streamlit UI
# ==============================
st.set_page_config(page_title="Smart Job Finder", page_icon="💼", layout="wide")
st.title("💼 Smart Job Finder — Resume + AI Web Search")

with st.sidebar:
    st.header("🔍 Job Filters")
    filters = {
        "location": st.text_input("Location (optional)"),
        "company": st.text_input("Company (optional)"),
        "keywords": st.text_input("Keywords (optional)"),
        "work_type": st.selectbox("Work Type", ["Any", "Remote", "Hybrid", "On-site"]),
    }
    posted_within_days = st.slider("Show jobs posted within (days):", 1, 30, 7)
    search_mode = st.radio(
        "Search Mode",
        ["Normal Search", "Normal + AI Summary", "Gemini-only Search"],
        index=0
    )

if "matched_jobs" not in st.session_state:
    st.session_state["matched_jobs"] = None

resume_file = st.file_uploader("📄 Upload your Resume (PDF only)", type=["pdf"])

if resume_file and st.button("Submit Resume"):
    with st.spinner("⏳ Extracting skills from your resume..."):
        resume_text = extract_resume_text(resume_file)
        skills = extract_skills(resume_text)
        exp = extract_experience(resume_text)
        st.session_state["skills"] = skills
    st.success(f"✅ Found Skills: {', '.join(skills)} | Experience: {exp}")

    if search_mode == "Normal Search":
        jobs = search_jobs(skills, filters)
        matched = match_jobs(skills, jobs, posted_within_days)
    elif search_mode == "Normal + AI Summary":
        jobs = search_jobs(skills, filters)
        matched = match_jobs(skills, jobs, posted_within_days)
        matched = add_ai_summaries(matched, skills)
    else:
        matched, msg = ai_web_search(skills, filters["keywords"], filters["company"], filters["location"], posted_within_days)
        st.info(msg)

    st.session_state["matched_jobs"] = matched

if st.session_state["matched_jobs"] is not None and not st.session_state["matched_jobs"].empty:
    st.success("🎯 Job results ready:")
    st.dataframe(st.session_state["matched_jobs"])
    csv = st.session_state["matched_jobs"].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Results as CSV", csv, "matched_jobs.csv", "text/csv")

    st.subheader("📧 Send job results to your email")
    user_email = st.text_input("Enter your email address:", placeholder="example@gmail.com")
    if st.button("Send Email Results"):
        send_email_with_jobs(st.session_state["matched_jobs"], user_email)
else:
    st.info("Upload your resume and click Submit to start the search.")
