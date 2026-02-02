import os
import json
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup
from openai import OpenAI

# -------------------------
# 1️⃣ Gmail Authentication
# -------------------------
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

# -------------------------
# 2️⃣ Job log (avoid sending reposts)
# -------------------------
SEEN_JOBS_FILE = "seen_jobs.json"

def load_seen_jobs():
    """Load set of job URLs we've already sent."""
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return set()

def save_seen_jobs(seen):
    """Persist seen job URLs to file."""
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)

def url_from_link(link):
    """Extract URL from 'text — href' format."""
    if " — " in link:
        return link.rsplit(" — ", 1)[-1].strip()
    return link

# -------------------------
# 3️⃣ Get unread Google Alert emails
# -------------------------
def get_unread_alerts(service):
    """Return list of unread messages in the inbox (ignoring from filter)."""
    results = service.users().messages().list(
        userId="me",
        q="is:unread"
    ).execute()

    messages = results.get("messages", [])
    print(f"Found {len(messages)} unread messages")
    return messages



# -------------------------
# 4️⃣ Extract links from single email
# -------------------------
def extract_links(service, msg_id):
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    payload = msg["payload"]
    parts = payload.get("parts", [])

    for part in parts:
        if part["mimeType"] == "text/html":
            data = part["body"]["data"]
            html = base64.urlsafe_b64decode(data).decode()
            soup = BeautifulSoup(html, "html.parser")

            links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                text = a.get_text(strip=True)
                if href and "http" in href:
                    links.append(f"{text} — {href}")

            return links
    return []

# -------------------------
# 5️⃣ Collect all links & mark emails as read
# -------------------------
def collect_all_links(service):
    messages = get_unread_alerts(service)
    all_links = []

    for m in messages:
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()

        # Get the 'From' header
        headers = msg["payload"].get("headers", [])
        from_header = next((h["value"] for h in headers if h["name"] == "From"), "")
        if "googlealerts-noreply@google.com" not in from_header:
            continue  # skip emails that aren’t from your project address

        # Extract links from email
        links = extract_links(service, m["id"])
        all_links.extend(links)

        # Mark email as read
        service.users().messages().modify(
            userId="me",
            id=m["id"],
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    # Remove duplicates
    unique_links = list(dict.fromkeys(all_links))  # preserves order
    return unique_links


# -------------------------
# 6️⃣ Master resume & tailored resumes
# -------------------------
MASTER_RESUME_FILE = "master_resume.txt"

def load_master_resume():
    """Load the master resume. Raises FileNotFoundError if missing."""
    if not os.path.exists(MASTER_RESUME_FILE):
        raise FileNotFoundError(
            f"Master resume not found. Create '{MASTER_RESUME_FILE}' in the project folder "
            "with your full resume (skills, experience, education, etc.)."
        )
    with open(MASTER_RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()

# -------------------------
# 7️⃣ Summarize jobs & generate tailored resumes
# -------------------------
client = OpenAI()  # Make sure OPENAI_API_KEY is set in environment variables

def generate_digest_with_tailored_resumes(master_resume, job_text):
    """Filter jobs, group duplicates, and generate a tailored resume for each job."""
    prompt = f"""
You are helping a job seeker. You have their MASTER RESUME and a list of JOB POSTINGS from Google Alerts.

MASTER RESUME:
---
{master_resume}
---

JOB POSTINGS (text — url format):
{job_text}

TASK:
1. Filter: Keep ONLY computer science/software jobs in Utah OR remote roles available in Utah. Ignore non-technical jobs, career advice, recruiter spam.
2. Group: When the same job (same role, same company) appears on multiple sites, treat as ONE job and list all links.
3. For EACH qualifying job: Output the job details (title, company, location, links) followed by a TAILORED VERSION of the master resume for that specific job.

For each tailored resume:
- Modify the professional summary to emphasize fit for that role
- Reorder and emphasize relevant bullet points and skills
- Adjust keyword emphasis to match the posting
- Keep all factual content—do not invent experience
- Maintain standard resume structure (contact, summary, experience, skills, education)

OUTPUT FORMAT (repeat for each job):

========================================
JOB: [Title] at [Company] — [Location]
Links:
- [url 1]
- [url 2] (if same job on multiple sites)
========================================

TAILORED RESUME:
[Full tailored resume for this job—use same sections as master resume]

========================================

"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )
    return response.output_text

# -------------------------
# 8️⃣ Send summary email
# -------------------------
def send_summary_email(service, summary):
    message = MIMEText(summary)
    message["to"] = "chancehardman71@gmail.com"  # <-- replace with your email
    message["subject"] = "Daily Utah CS Job Digest"

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

# -------------------------
# 9️⃣ Main
# -------------------------
if __name__ == "__main__":
    service = get_gmail_service()

    try:
        master_resume = load_master_resume()
    except FileNotFoundError as e:
        print(e)
        exit(1)

    links = collect_all_links(service)
    if not links:
        print("No new alerts today.")
        exit()

    seen = load_seen_jobs()
    new_links = [lnk for lnk in links if url_from_link(lnk) not in seen]

    if not new_links:
        print("No new jobs (all already sent). Skipping email.")
        exit()

    combined_text = "\n".join(new_links)
    digest = generate_digest_with_tailored_resumes(master_resume, combined_text)

    send_summary_email(service, digest)

    for lnk in new_links:
        seen.add(url_from_link(lnk))
    save_seen_jobs(seen)

    print("Daily job digest with tailored resumes sent!")
