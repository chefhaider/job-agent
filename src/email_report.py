import json
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path

# ── Configuration (loaded from environment / .env) ───────────────────────────
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("GMAIL_APP")  # Gmail App Password
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
JOBS_JSON_PATH = "output/job_descriptions.json"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
# ── Load JSON Data ────────────────────────────────────────────────────────────
def load_jobs(json_path: str) -> list:
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"❌ JSON not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("jobs", [])

# ── Build HTML Email Body ─────────────────────────────────────────────────────
def build_html_email(jobs: list) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2c3e50; margin: 0; padding: 20px; background: #f5f7fa; }}
            .container {{ max-width: 750px; margin: 0 auto; background: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
            .header {{ text-align: center; padding-bottom: 20px; border-bottom: 2px solid #eaecef; margin-bottom: 25px; }}
            .header h1 {{ margin: 0; color: #1a202c; font-size: 24px; }}
            .header p {{ margin: 5px 0 0; color: #718096; font-size: 14px; }}
            .job-card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 15px; background: #f8fafc; }}
            .job-title {{ font-size: 18px; font-weight: 700; color: #2d3748; margin: 0 0 5px; }}
            .company {{ font-size: 16px; color: #3182ce; font-weight: 500; margin: 5px 0; }}
            .meta {{ display: flex; flex-wrap: wrap; gap: 15px; margin-top: 10px; font-size: 14px; color: #4a5568; }}
            .meta a {{ color: #3182ce; text-decoration: none; word-break: break-all; }}
            .meta a:hover {{ text-decoration: underline; }}
            .resume-path {{ 
                background: #edf2f7; 
                padding: 8px 12px; 
                border-radius: 6px; 
                font-family: 'Courier New', monospace; 
                font-size: 13px; 
                color: #2d3748; 
                margin-top: 10px; 
                display: inline-block;
                word-break: break-all;
                border: 1px solid #cbd5e0;
            }}
            .footer {{ text-align: center; margin-top: 25px; font-size: 12px; color: #a0aec0; border-top: 1px solid #e2e8f0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Job Applications Summary</h1>
                <p>Generated on {timestamp}</p>
            </div>
    """

    for i, job in enumerate(jobs, 1):
        title = job.get("job_title", "N/A")
        company = job.get("company_name", "N/A")
        url = job.get("job_url", "#")
        resume_path = job.get("resume_file_path", "Not generated")
        
        html += f"""
            <div class="job-card">
                <div class="job-title">{i}. {title}</div>
                <div class="company">{company}</div>
                <div class="meta">
                    <span>🔗 <a href="{url}" target="_blank">LinkedIn Posting</a></span>
                </div>
                <div class="resume-path">{resume_path}</div>
            </div>
        """

    html += f"""
            <div class="footer">
                Automated Pipeline • {len(jobs)} jobs processed • No attachments included
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ── Send Email (NO ATTACHMENTS) ───────────────────────────────────────────────
def send_email(sender: str, password: str, receiver: str, subject: str, html_body: str):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    
    # Attach HTML body only
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ Email successfully sent to {receiver}")
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication failed. Check your Gmail App Password & 2FA settings.")
        raise
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    jobs = load_jobs(JOBS_JSON_PATH)
    if not jobs:
        print("⚠️ No jobs found in JSON.")
        return

    print(f"📝 Building email for {len(jobs)} jobs...")
    html_body = build_html_email(jobs)
    
    subject = f"Job Applications Summary ({len(jobs)} Jobs) - {datetime.now().strftime('%Y-%m-%d')}"
    
    print(f"📤 Sending email to {RECEIVER_EMAIL}...")
    send_email(
        sender=SENDER_EMAIL,
        password=SENDER_PASSWORD,
        receiver=RECEIVER_EMAIL,
        subject=subject,
        html_body=html_body,
    )

if __name__ == "__main__":
    main()