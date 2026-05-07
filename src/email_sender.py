import logging
from typing import Optional
from datetime import datetime

import requests
from src.config import RESEND_API_KEY, SENDER_EMAIL, SENDER_NAME

logger = logging.getLogger(__name__)

class EmailSender:
    """Send emails via Resend API."""

    def __init__(self):
        self.api_key = RESEND_API_KEY
        self.sender_email = SENDER_EMAIL
        self.sender_name = SENDER_NAME
        self.base_url = "https://api.resend.com"

    def send_report(self, recipient_email: str, business_name: str, full_report_html: str, summary_html: str) -> bool:
        """Send daily competitive report email."""
        subject = f"[Competitive Intel] Daily Report — {datetime.now().strftime('%Y-%m-%d')}"

        # Combine both reports into email body
        email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
        .section-break {{ height: 40px; border-top: 2px solid #e0e0e0; margin: 40px 0; }}
        .section-title {{ color: #1e40af; font-size: 20px; font-weight: bold; margin: 30px 0 15px 0; }}
    </style>
</head>
<body>
<div class="container">

<div class="section-title">📋 Executive Summary</div>
{summary_html}

<div class="section-break"></div>

<div class="section-title">📊 Full Report</div>
{full_report_html}

</div>
</body>
</html>
"""

        return self._send_email(
            to=recipient_email,
            subject=subject,
            html=email_html
        )

    def send_error_report(self, recipient_email: str, error_message: str) -> bool:
        """Send error notification email."""
        subject = "[Competitive Intel] Crawler Error Report"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .error-box {{ background: #fee2e2; border: 1px solid #fca5a5; padding: 15px; border-radius: 8px; }}
        .error-title {{ color: #dc2626; font-weight: bold; margin-bottom: 10px; }}
    </style>
</head>
<body>
<div class="container">
    <h2>⚠️ Crawler Error</h2>
    <div class="error-box">
        <div class="error-title">An error occurred during the daily crawl:</div>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{error_message}</pre>
    </div>
    <p>The next crawl will run at the scheduled time. If errors persist, please check your configuration.</p>
    <p style="color: #666; font-size: 12px;">Timestamp: {datetime.now().isoformat()}</p>
</div>
</body>
</html>
"""

        return self._send_email(
            to=recipient_email,
            subject=subject,
            html=html
        )

    def _send_email(self, to: str, subject: str, html: str) -> bool:
        """Send email via Resend API."""
        if not self.api_key:
            logger.error("RESEND_API_KEY not configured")
            return False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": f"{self.sender_name} <{self.sender_email}>",
            "to": to,
            "subject": subject,
            "html": html
        }

        try:
            response = requests.post(
                f"{self.base_url}/emails",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Email sent to {to}")
                return True
            else:
                logger.error(f"Resend API error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

email_sender = EmailSender()
