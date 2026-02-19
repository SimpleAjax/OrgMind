import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Optional

from orgmind.platform.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_tls = settings.SMTP_TLS

    def send_html_email(self, to_emails: List[str], subject: str, html_content: str) -> bool:
        """
        Send an HTML email to a list of recipients.
        """
        if not to_emails:
            return False
            
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to_emails)

        part = MIMEText(html_content, "html")
        msg.attach(part)

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.user and self.password:
                    server.login(self.user, self.password)
                
                server.sendmail(self.from_email, to_emails, msg.as_string())
            
            logger.info(f"Email sent to {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
