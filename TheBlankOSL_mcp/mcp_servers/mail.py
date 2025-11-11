from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass
from typing import Optional, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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
    """Result object returned after sending an email."""
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
    smtp_port: Optional[int] = None,
    attachments: Optional[List[str]] = None
) -> EmailResult:
    """
    Send an email via SMTP, optionally with attachments.

    Args:
        to_email (str): Recipient email address.
        subject (str): Email subject line.
        body (str): Email body in plain text.
        from_email (str, optional): Sender email address. Defaults to SMTP username or environment variable.
        smtp_username (str, optional): SMTP login username. Defaults to environment variable SMTP_USERNAME.
        smtp_password (str, optional): SMTP login password. Defaults to environment variable SMTP_PASSWORD.
        smtp_server (str, optional): SMTP server hostname. Defaults to environment variable SMTP_SERVER or "smtp.gmail.com".
        smtp_port (int, optional): SMTP server port. Defaults to environment variable SMTP_PORT or 587.
        attachments (List[str], optional): List of local file paths to attach. If a file is missing, email sending fails.

    Returns:
        EmailResult: Dataclass with the following fields:
            - success (bool): True if email was sent successfully, False otherwise.
            - message (str): Human-readable success or error message.
            - from_email (str): Sender email address.
            - to_email (str): Recipient email address.
            - subject (str): Email subject.
            - error (str, optional): Detailed error message if sending failed.

    Raises:
        None: Errors are captured and returned in the EmailResult object instead of raising exceptions.
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

        # Attach files if any
        if attachments:
            for file_path in attachments:
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{os.path.basename(file_path)}"'
                        )
                        message.attach(part)
                else:
                    return EmailResult(
                        success=False,
                        message=f"Attachment not found: {file_path}",
                        from_email=sender,
                        to_email=to_email,
                        subject=subject,
                        error="File does not exist"
                    )

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

    except smtplib.SMTPAuthenticationError:
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
