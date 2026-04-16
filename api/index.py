"""
leiten-webhook — Vercel Serverless Function
Webhook receiver for GitHub Pull Request events.
Sends an email notification to the PR author before merge.
"""

import os
import hmac
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import BaseHTTPRequestHandler
import json


# -- Config from environment variables --
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature (HMAC SHA-256)."""
    if not WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Send an email via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"SMTP credentials not configured - skipping email to {to_email}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def build_pr_email(action: str, pr: dict, repo: dict, sender: dict) -> tuple:
    """Build subject and HTML body for a PR notification."""
    pr_title = pr.get("title", "Sin titulo")
    pr_number = pr.get("number", "?")
    pr_url = pr.get("html_url", "#")
    repo_name = repo.get("full_name", "unknown")
    base_branch = pr.get("base", {}).get("ref", "main")
    head_branch = pr.get("head", {}).get("ref", "?")
    author = sender.get("login", "alguien")

    action_map = {
        "opened": "se abrio",
        "reopened": "se reabrio",
        "synchronize": "se actualizo",
        "ready_for_review": "esta listo para revision",
    }
    action_text = action_map.get(action, action)

    subject = f"[{repo_name}] PR #{pr_number} {action_text}: {pr_title}"

    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Notificacion de Pull Request</h2>
            <p style="margin: 5px 0 0; opacity: 0.8;">{repo_name}</p>
        </div>
        <div style="border: 1px solid #e0e0e0; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <p>Hola <strong>{author}</strong>,</p>
            <p>Tu Pull Request <strong>#{pr_number}</strong> {action_text}.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Titulo</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>{pr_title}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Rama</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{head_branch}</code> &rarr; <code>{base_branch}</code></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Estado</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{action_text.capitalize()}</td>
                </tr>
            </table>
            <p>
                <a href="{pr_url}"
                   style="display: inline-block; background: #0366d6; color: white;
                          padding: 10px 20px; border-radius: 5px; text-decoration: none;">
                    Ver Pull Request en GitHub
                </a>
            </p>
            <p style="color: #999; font-size: 12px; margin-top: 20px;">
                Recorda que este PR aun no fue mergeado. Revisa los cambios antes de aprobar.
            </p>
        </div>
    </div>
    """
    return subject, body


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for GitHub webhooks."""

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Health check."""
        self._send_json(200, {"status": "ok", "service": "leiten-webhook"})

    def do_POST(self):
        """Handle GitHub webhook POST requests."""
        # 1. Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 2. Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(body, signature):
            self._send_json(403, {"error": "Invalid signature"})
            return

        # 3. Check event type
        event = self.headers.get("X-GitHub-Event", "")
        if event == "ping":
            self._send_json(200, {"message": "pong"})
            return

        if event != "pull_request":
            self._send_json(200, {"message": f"Event '{event}' ignored"})
            return

        # 4. Parse payload
        payload = json.loads(body)
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Only notify on meaningful actions
        notify_actions = {"opened", "reopened", "ready_for_review"}
        if action not in notify_actions:
            self._send_json(200, {"message": f"Action '{action}' ignored"})
            return

        # 5. Get author email
        author_email = (
            pr.get("head", {}).get("user", {}).get("email")
            or pr.get("user", {}).get("email")
            or payload.get("sender", {}).get("email")
        )

        if not author_email:
            self._send_json(200, {
                "message": "No author email available",
                "hint": "The user's GitHub email may be private.",
            })
            return

        # 6. Build and send email
        subject, email_body = build_pr_email(action, pr, repo, sender)
        sent = send_email(author_email, subject, email_body)

        self._send_json(200, {
            "message": "Notification sent" if sent else "Email skipped (check config)",
            "pr": pr.get("number"),
            "author": sender.get("login"),
        })
