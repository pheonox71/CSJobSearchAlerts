# CS Job Search Alerts

A Python tool that monitors your Gmail for Google Alert emails about job postings, filters them for relevance, groups duplicates across job boards, and emails you a digest with **tailored resume versions** for each job.

## How It Works

1. **Gmail + Google Alerts** — You use a Gmail account that receives [Google Alerts](https://www.google.com/alerts) for the job keywords you care about (e.g., "software engineer Utah", "developer remote Utah").

2. **This program** — When you run it, it:
   - Reads unread emails from Gmail that are from `googlealerts-noreply@google.com`
   - Extracts job links from those emails and marks them as read
   - Filters for computer science/software jobs in Utah or remote roles available in Utah
   - Groups the same job when it appears on multiple sites (Indeed, LinkedIn, Glassdoor, etc.)
   - Skips jobs you’ve already been sent (no repeat alerts)
   - Generates a tailored resume for each job using your master resume and OpenAI
   - Emails you one digest with each job and its tailored resume

## Prerequisites

- Python 3.x
- A Gmail account that receives Google Alerts
- [Google Alerts](https://www.google.com/alerts) set up with job search terms (delivered to your Gmail)
- [Google Cloud project](https://console.cloud.google.com/) with Gmail API enabled
- [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

### 1. Google Alerts

1. Go to [google.com/alerts](https://www.google.com/alerts)
2. Create alerts for your job search terms (e.g., `software engineer Utah`, `developer remote`)
3. Set delivery to **Email** and use the same Gmail account you’ll connect to this program

### 2. Gmail API

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project (or use an existing one)
2. Enable the **Gmail API**
3. Go to **Credentials** → **Create credentials** → **OAuth client ID**
4. Choose **Desktop app**, then download the JSON
5. Save it as `credentials.json` in the project folder

### 3. Install Dependencies

```bash
pip install google-api-python-client google-auth-oauthlib google-auth beautifulsoup4 openai
```

### 4. Configure

- **`master_resume.txt`** — Add your full resume (contact, summary, experience, skills, education, projects). The program uses this to generate tailored versions per job.
- **`config.json`** — Copy `config.example.json` to `config.json` and set `recipient_email` to the address where you want the digest sent.
- **Environment** — Set your OpenAI API key:
  ```bash
  set OPENAI_API_KEY=your-key-here
  ```

## Usage

```bash
python main.py
```

On first run, a browser window opens for Gmail OAuth. After that, tokens are stored in `token.json`.

- If there are no new alert emails, it exits with no email sent.
- If all jobs have already been sent, it skips the email.
- Otherwise, it sends one digest email with each job and its tailored resume.

## Project Structure

| File | Purpose |
|------|---------|
| `main.py` | Main script: Gmail, filtering, resume tailoring, email |
| `config.example.json` | Template for config; copy to `config.json` and add your recipient email |

## Files Hidden from Public View (Git-Ignored)

The following files are listed in `.gitignore` and are **not** committed to the repository. They contain private data and should stay on your machine only:

| File | Purpose | Setup |
|------|---------|-------|
| `master_resume.txt` | Your full resume; used to generate tailored versions per job | Create and add your resume content |
| `credentials.json` | Gmail API OAuth client secrets (from Google Cloud) | Download from Cloud Console and save here |
| `token.json` | Gmail OAuth tokens (created automatically on first run) | Created when you complete Gmail OAuth |
| `config.json` | Recipient email for the job digest | Copy `config.example.json` to `config.json` and add your email |
| `seen_jobs.json` | URLs of jobs already sent (avoids repeats) | Created automatically when jobs are sent |

## Customization

- **Job filter** — Edit the prompt in `generate_digest_with_tailored_resumes()` to change location, job type, or criteria.
- **Resume tailoring** — Adjust your `master_resume.txt`; the model keeps the same structure but reorders and emphasizes content per job.
