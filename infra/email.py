# infra/email.py
"""Email service for sending notifications."""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = self._get_smtp_port()
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.smtp_from = os.getenv("SMTP_FROM")
    
    def _get_smtp_port(self) -> int:
        """Get SMTP port with validation and fallback."""
        try:
            port_str = os.getenv("SMTP_PORT", "587")
            port = int(port_str)
            if port <= 0 or port > 65535:
                print(f"⚠️ Invalid SMTP_PORT: {port}. Using default 587.")
                return 587
            return port
        except (ValueError, TypeError):
            print(f"⚠️ Invalid SMTP_PORT format. Using default 587.")
            return 587
    
    def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """Send email via SMTP."""
        if not all([self.smtp_host, self.smtp_user, self.smtp_pass, self.smtp_from]):
            print("⚠️ Missing SMTP configuration")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_from
            msg["To"] = to_email
            
            # Add text part
            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def send_notification(self, to_email: str, title: str, message: str) -> bool:
        """Send a notification email."""
        subject = f"Q3 Automatiza - {title}"
        return self.send_email(to_email, subject, message)

# Global email service instance
email_service = EmailService()