# CS Job Search Alerts

A Python web app that monitors your Gmail for Google Alert emails about job postings, filters them for relevance, groups duplicates across job boards, and displays a digest with **tailored resume versions** for each job in a clean web UI.

## How It Works

1. **Gmail + Google Alerts** — You use a Gmail account that receives [Google Alerts](https://www.google.com/alerts) for the job keywords you care about (e.g., "software engineer Utah", "developer remote Utah").

2. **This program** — When you run it and click **Fetch Jobs** in the browser:
   - Reads unread emails from Gmail that are from `googlealerts-noreply@google.com`
   - Extracts job links from those emails and marks them as read
   - Filters for computer science/software jobs in Utah or remote roles available in Utah
   - Groups the same job when it appears on multiple sites (Indeed, LinkedIn, Glassdoor, etc.)
   - Skips jobs you’ve already seen (no repeat alerts)
   - Generates a tailored resume for each job using your master resume and OpenAI
   - Displays each job and its tailored resume in the web UI

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
pip install -r requirements.txt
```

### 4. Configure

- **`master_resume.txt`** — Add your full resume (contact, summary, experience, skills, education, projects). The program uses this to generate tailored versions per job.
- **Environment** — Set your OpenAI API key:
  ```bash
  set OPENAI_API_KEY=your-key-here
  ```

## Usage

```bash
python main.py
```

Then open **http://localhost:5000** in your browser and click **Fetch Jobs**.

On first fetch, a browser window opens for Gmail OAuth. After that, tokens are stored in `token.json`.

- If there are no new alert emails, the UI shows a message.
- If all jobs have already been seen, it skips processing.
- Otherwise, each job and its tailored resume appear in the web UI.

## Project Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point; runs the Flask web server |
| `app.py` | Flask app and API routes |
| `job_processor.py` | Gmail, filtering, resume tailoring logic |
| `templates/index.html` | Web UI |

## Files Hidden from Public View (Git-Ignored)

The following files are listed in `.gitignore` and are **not** committed to the repository. They contain private data and should stay on your machine only:

| File | Purpose | Setup |
|------|---------|-------|
| `master_resume.txt` | Your full resume; used to generate tailored versions | Create and add your resume content |
| `credentials.json` | Gmail API OAuth client secrets (from Google Cloud) | Download from Cloud Console and save here |
| `token.json` | Gmail OAuth tokens (created automatically on first fetch) | Created when you complete Gmail OAuth |
| `seen_jobs.json` | URLs of jobs already seen (avoids repeats) | Created automatically when jobs are fetched |

## Customization

- **Job filter** — Edit the prompt in `generate_digest_with_tailored_resumes()` in `job_processor.py` to change location, job type, or criteria.
- **Resume tailoring** — Adjust your `master_resume.txt`; the model keeps the same structure but reorders and emphasizes content per job.
