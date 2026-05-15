import base64
import logging
from typing import Optional, List, Dict
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
        """Send daily competitive report email with PDF attachment."""
        report_date = datetime.now().strftime('%Y-%m-%d')
        subject = f"[Competitive Intel] Daily Report — {report_date}"

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
        .pdf-note {{ background: #f0f9ff; border-left: 4px solid #1e40af; padding: 12px 16px; margin: 20px 0; font-size: 14px; color: #1e3a8a; }}
    </style>
</head>
<body>
<div class="container">

<div class="pdf-note">
    📎 The full report is attached as a PDF for easy sharing or archiving.
</div>

<div class="section-title">📋 Executive Summary</div>
{summary_html}

<div class="section-break"></div>

<div class="section-title">📊 Full Report</div>
{full_report_html}

</div>
</body>
</html>
"""

        # Generate PDF version of the report for attachment
        attachments: List[Dict] = []
        try:
            pdf_bytes = self._html_to_pdf(
                business_name=business_name,
                report_date=report_date,
                summary_html=summary_html,
                full_report_html=full_report_html,
            )
            if pdf_bytes:
                safe_business = "".join(
                    c if c.isalnum() or c in ("-", "_") else "_" for c in business_name
                )
                pdf_filename = f"competitive-report-{safe_business}-{report_date}.pdf"
                attachments.append({
                    "filename": pdf_filename,
                    "content": base64.b64encode(pdf_bytes).decode("utf-8"),
                })
                logger.info(f"Generated PDF attachment ({len(pdf_bytes)} bytes): {pdf_filename}")
        except Exception as e:
            # PDF generation failure should not block email delivery
            logger.warning(f"PDF generation failed, sending email without attachment: {e}")

        return self._send_email(
            to=recipient_email,
            subject=subject,
            html=email_html,
            attachments=attachments,
        )

    def _html_to_pdf(self, business_name: str, report_date: str, summary_html: str, full_report_html: str) -> Optional[bytes]:
        """Render the report HTML to PDF using Playwright (Chromium headless).

        Returns PDF bytes on success, None on failure.
        Playwright is already a project dependency (used by the crawler).
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed; skipping PDF generation")
            return None

        # Print-optimized HTML wrapper with @page rules and PDF-friendly typography
        pdf_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Competitive Intelligence Report — {business_name} — {report_date}</title>
    <style>
        @page {{
            size: A4;
            margin: 18mm 14mm 18mm 14mm;
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }}
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #111;
            margin: 0;
            padding: 0;
        }}
        .pdf-cover {{
            text-align: center;
            padding: 40mm 0 30mm;
            border-bottom: 2px solid #1e40af;
            margin-bottom: 30px;
            page-break-after: always;
        }}
        .pdf-cover h1 {{ color: #1e40af; font-size: 28pt; margin: 0 0 12px 0; }}
        .pdf-cover .business {{ font-size: 18pt; color: #333; margin: 8px 0; }}
        .pdf-cover .date {{ font-size: 12pt; color: #666; margin-top: 16px; }}
        h1, h2, h3, h4 {{ color: #1e40af; page-break-after: avoid; }}
        h2 {{ font-size: 18pt; margin-top: 24px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
        h3 {{ font-size: 14pt; margin-top: 18px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 12px 0; page-break-inside: avoid; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; font-size: 10pt; }}
        th {{ background: #f3f4f6; font-weight: 600; }}
        .section-title {{ color: #1e40af; font-size: 16pt; font-weight: bold; margin: 28px 0 12px 0; page-break-after: avoid; }}
        .section-break {{ height: 24px; border-top: 1px solid #e5e7eb; margin: 24px 0; }}
        ul, ol {{ margin: 8px 0; padding-left: 22px; }}
        li {{ margin: 4px 0; }}
        a {{ color: #1d4ed8; text-decoration: none; }}
        .container {{ max-width: 100%; }}
    </style>
</head>
<body>
    <div class="pdf-cover">
        <h1>Competitive Intelligence Report</h1>
        <div class="business">{business_name}</div>
        <div class="date">{report_date}</div>
    </div>

    <div class="container">
        <div class="section-title">Executive Summary</div>
        {summary_html}

        <div class="section-break"></div>

        <div class="section-title">Full Report</div>
        {full_report_html}
    </div>
</body>
</html>
"""

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(pdf_html, wait_until="networkidle")
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "18mm", "right": "14mm", "bottom": "18mm", "left": "14mm"},
                )
                browser.close()
                return pdf_bytes
        except Exception as e:
            logger.error(f"Playwright PDF rendering failed: {e}")
            return None

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

    def _send_email(self, to: str, subject: str, html: str, attachments: Optional[List[Dict]] = None) -> bool:
        """Send email via Resend API.

        attachments: list of {"filename": str, "content": base64_str} dicts (Resend format).
        """
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

        if attachments:
            payload["attachments"] = attachments

        try:
            response = requests.post(
                f"{self.base_url}/emails",
                json=payload,
                headers=headers,
                timeout=30  # PDF attachments may take longer to upload
            )

            if response.status_code == 200:
                attach_note = f" with {len(attachments)} attachment(s)" if attachments else ""
                logger.info(f"Email sent to {to}{attach_note}")
                return True
            else:
                logger.error(f"Resend API error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

email_sender = EmailSender()
