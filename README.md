# 🤖 AI Job Finder

AI Job Finder is an intelligent **Streamlit web app** that helps job seekers automatically find job postings that match their resume skills and experience.  
It scans the uploaded resume, extracts key skills, estimates work experience, and searches for relevant jobs on top product-based company career portals.

---

## 🚀 Features

- 📂 **Resume Upload (PDF only)** – Upload your resume and extract text automatically.  
- 🧠 **Smart Skill Extraction** – Detects technical and professional skills using keyword matching.  
- ⏳ **Experience Calculation** – Reads experience duration and converts it into total years.  
- 🌐 **Live Job Search** – Fetches job listings from:
  - Google Careers  
  - Amazon Jobs  
  - Microsoft Careers  
  - Meta Careers  
  - Apple Careers  
  - LinkedIn Jobs  
- 🔍 **Advanced Filters** – Search by location, company, keywords, and posting date range.  
- 💌 **Email Alerts** – Sends top 5 job matches and attaches all results in a CSV file.  
- 📊 **Result Table + CSV Download** – View and export all matching jobs.  
- 🧾 **Secure Credentials** – API keys and email credentials are safely stored in `.streamlit/secrets.toml`.

---

## 🧰 Tech Stack

- **Python 3.x**
- **Streamlit** – Web App Framework  
- **Google Custom Search API** – Web Scraping/Search  
- **PyPDF2** – Resume Parsing  
- **RapidFuzz** – Fuzzy Skill Matching  
- **smtplib** – Email Automation  
- **Pandas** – Data Processing  

---

## ⚙️ Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/<your-username>/ai-job-finder.git
cd ai-job-finder
