"""Core job processing logic: Gmail, link extraction, digest generation."""

import os
import json
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup
from openai import OpenAI

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SEEN_JOBS_FILE = "seen_jobs.json"
MASTER_RESUME_FILE = "master_resume.txt"

client = OpenAI()


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


def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)


def url_from_link(link):
    if " — " in link:
        return link.rsplit(" — ", 1)[-1].strip()
    return link


def get_unread_alerts(service):
    results = service.users().messages().list(
        userId="me",
        q="is:unread"
    ).execute()
    return results.get("messages", [])


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


def collect_all_links(service):
    messages = get_unread_alerts(service)
    all_links = []

    for m in messages:
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()

        headers = msg["payload"].get("headers", [])
        from_header = next((h["value"] for h in headers if h["name"] == "From"), "")
        if "googlealerts-noreply@google.com" not in from_header:
            continue

        links = extract_links(service, m["id"])
        all_links.extend(links)

        service.users().messages().modify(
            userId="me",
            id=m["id"],
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    return list(dict.fromkeys(all_links))


def load_master_resume():
    if not os.path.exists(MASTER_RESUME_FILE):
        raise FileNotFoundError(
            f"Master resume not found. Create '{MASTER_RESUME_FILE}' in the project folder."
        )
    with open(MASTER_RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()


def generate_digest_with_tailored_resumes(master_resume, job_text):
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
3. For EACH qualifying job: Output the job details (title, company, location, links), a brief JOB SUMMARY, then a TAILORED VERSION of the master resume for that specific job.

For each job summary:
- Write 2-4 sentences summarizing the role, key requirements, and why it might be a good fit for this candidate
- Base it on the job posting content; be specific and concise

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

JOB SUMMARY:
[2-4 sentence summary of the role, key requirements, and fit for this candidate]

TAILORED RESUME:
[Full tailored resume for this job—use same sections as master resume]

========================================

"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )
    return response.output_text


def parse_digest(digest_text):
    """Parse digest text into list of job dicts with title, company, location, links, resume."""
    jobs = []
    blocks = digest_text.split("========================================")

    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if not block:
            i += 1
            continue

        if block.upper().startswith("JOB:"):
            job_info = {"title": "", "company": "", "location": "", "links": [], "summary": "", "resume": ""}

            # Parse JOB line: "JOB: [Title] at [Company] — [Location]"
            first_line = block.split("\n")[0]
            if " — " in first_line:
                before_loc, location = first_line.rsplit(" — ", 1)
                job_info["location"] = location.strip()
                if " at " in before_loc and before_loc.upper().startswith("JOB:"):
                    _, rest = before_loc.split("JOB:", 1)
                    rest = rest.strip()
                    if " at " in rest:
                        title, company = rest.rsplit(" at ", 1)
                        job_info["title"] = title.strip()
                        job_info["company"] = company.strip()

            # Extract links (lines starting with - after "Links:")
            lines = block.split("\n")
            in_links = False
            for line in lines:
                if line.strip().lower().startswith("links:"):
                    in_links = True
                    continue
                if in_links and line.strip().startswith("-"):
                    link = line.strip()[1:].strip()
                    if link and "http" in link:
                        job_info["links"].append(link)

            # Next block = JOB SUMMARY + TAILORED RESUME
            if i + 1 < len(blocks):
                next_block = blocks[i + 1].strip()
                nb_upper = next_block.upper()
                if "JOB SUMMARY" in nb_upper:
                    idx = nb_upper.find("JOB SUMMARY:")
                    after_label = next_block[idx + len("JOB SUMMARY:"):].strip()
                    if "TAILORED RESUME" in nb_upper:
                        ridx = nb_upper.find("TAILORED RESUME:", idx)
                        summary_text = next_block[idx + len("JOB SUMMARY:"):ridx].strip()
                        resume_text = next_block[ridx + len("TAILORED RESUME:"):].strip()
                        job_info["summary"] = summary_text
                        job_info["resume"] = resume_text
                    else:
                        job_info["summary"] = after_label
                elif "TAILORED RESUME" in nb_upper:
                    parts = next_block.split("\n", 1)
                    if len(parts) > 1:
                        job_info["resume"] = parts[1].strip()
                i += 1

            jobs.append(job_info)
        i += 1

    return jobs


def run_pipeline():
    """Fetch alerts, process, generate digest. Returns (digest_text, jobs_list, error)."""
    try:
        service = get_gmail_service()
        master_resume = load_master_resume()
    except FileNotFoundError as e:
        return None, [], str(e)

    links = collect_all_links(service)
    if not links:
        return None, [], "No new alerts today."

    seen = load_seen_jobs()
    new_links = [lnk for lnk in links if url_from_link(lnk) not in seen]

    if not new_links:
        return None, [], "No new jobs (all already seen)."

    combined_text = "\n".join(new_links)
    digest = generate_digest_with_tailored_resumes(master_resume, combined_text)
    jobs = parse_digest(digest)

    for lnk in new_links:
        seen.add(url_from_link(lnk))
    save_seen_jobs(seen)

    return digest, jobs, None
