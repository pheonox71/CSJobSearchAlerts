"""Flask web UI for CS Job Search Alerts."""

import io
import re
from flask import Flask, render_template, jsonify, request, send_file
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from job_processor import run_pipeline

app = Flask(__name__)


def sanitize_filename(name):
    """Remove characters invalid for filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip() or "resume"


def resume_to_pdf(resume_text):
    """Generate a PDF from resume text. Returns bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
    )
    story = []
    for line in resume_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;"), body_style))
    doc.build(story)
    return buffer.getvalue()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch", methods=["POST"])
def fetch_jobs():
    digest, jobs, error = run_pipeline()
    if error:
        return jsonify({"success": False, "error": error})
    return jsonify({"success": True, "jobs": jobs, "raw_digest": digest})


@app.route("/api/download-resume", methods=["POST"])
def download_resume():
    data = request.get_json()
    if not data or "resume" not in data:
        return jsonify({"error": "Missing resume content"}), 400

    title = data.get("title", "")
    company = data.get("company", "")
    location = data.get("location", "")
    resume_text = data["resume"]

    # Build filename: "Title at Company — Location resume.pdf"
    parts = []
    if title:
        parts.append(title)
    if company:
        parts.append(f"at {company}")
    if location:
        parts.append(f"— {location}")
    base_name = " ".join(parts) if parts else "resume"
    filename = f"{sanitize_filename(base_name)} resume.pdf"

    pdf_bytes = resume_to_pdf(resume_text)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
