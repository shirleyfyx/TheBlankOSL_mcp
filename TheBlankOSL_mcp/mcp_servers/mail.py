from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Load environment variables
load_dotenv()

# Email configuration from environment
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
DEFAULT_SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
DEFAULT_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Initialize MCP server
mcp = FastMCP("email")

@dataclass
class EmailResult:
    success: bool
    message: str
    from_email: str
    to_email: str
    subject: str
    error: Optional[str] = None

@mcp.tool()
async def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    smtp_username: Optional[str] = None,
    smtp_password: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None
) -> EmailResult:
    """Send an email via SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        from_email: Sender email address (optional, defaults to smtp_username or env variable)
        smtp_username: SMTP username (optional, defaults to env variable)
        smtp_password: SMTP password (optional, defaults to env variable)
        smtp_server: SMTP server address (optional, defaults to env variable or smtp.gmail.com)
        smtp_port: SMTP port (optional, defaults to env variable or 587)

    Returns:
        EmailResult object with send status
    """
    # Use defaults from environment if not provided
    username = smtp_username or DEFAULT_SMTP_USERNAME
    password = smtp_password or DEFAULT_SMTP_PASSWORD
    server = smtp_server or DEFAULT_SMTP_SERVER
    port = smtp_port or DEFAULT_SMTP_PORT
    sender = from_email or username

    if not username or not password:
        return EmailResult(
            success=False,
            message="SMTP credentials not provided",
            from_email=sender,
            to_email=to_email,
            subject=subject,
            error="Missing SMTP_USERNAME or SMTP_PASSWORD in environment or parameters"
        )

    try:
        # Create message
        message = MIMEMultipart()
        message["From"] = sender
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Connect to SMTP server and send email
        with smtplib.SMTP(server, port) as smtp_conn:
            smtp_conn.starttls()  # Enable TLS encryption
            smtp_conn.login(username, password)
            smtp_conn.send_message(message)

        return EmailResult(
            success=True,
            message=f"Email sent successfully to {to_email}",
            from_email=sender,
            to_email=to_email,
            subject=subject
        )

    except smtplib.SMTPAuthenticationError as e:
        return EmailResult(
            success=False,
            message="Authentication failed",
            from_email=sender,
            to_email=to_email,
            subject=subject,
            error="Check your username and password. For Gmail, use an App Password."
        )

    except Exception as e:
        return EmailResult(
            success=False,
            message="Failed to send email",
            from_email=sender,
            to_email=to_email,
            subject=subject,
            error=f"{type(e).__name__}: {str(e)}"
        )

if __name__ == "__main__":
    mcp.run(transport="stdio")