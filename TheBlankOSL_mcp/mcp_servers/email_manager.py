from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import decode_header
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel
import os

# Load environment variables
load_dotenv()

# Email configuration from environment
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
DEFAULT_IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
DEFAULT_IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
DEFAULT_SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
DEFAULT_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Initialize MCP server
mcp = FastMCP("email_manager")


@dataclass
class EmailResult:
    """Result object returned after sending an email."""

    success: bool
    message: str
    from_email: str
    to_email: str
    subject: str
    error: Optional[str] = None


@dataclass
class EmailMessage:
    """Represents an email message."""

    id: str
    subject: str
    from_email: str
    to_email: str
    date: str
    body: str
    has_attachments: bool
    is_read: bool


def decode_mime_header(header: str) -> str:
    """Decode MIME encoded email headers."""
    if not header:
        return ""

    decoded_parts = decode_header(header)
    result = []

    for content, encoding in decoded_parts:
        if isinstance(content, bytes):
            try:
                result.append(content.decode(encoding or "utf-8", errors="ignore"))
            except Exception:
                result.append(content.decode("utf-8", errors="ignore"))
        else:
            result.append(str(content))

    return "".join(result)


def extract_email_body(msg: email.message.Message) -> str:
    """Extract the body text from an email message."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Look for text/plain parts that are not attachments
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
                except Exception:
                    pass
            # If no plain text, try html
            elif (
                content_type == "text/html"
                and not body
                and "attachment" not in content_disposition
            ):
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="ignore")
        except Exception:
            body = str(msg.get_payload())

    return body.strip()


class CustomRequest(BaseModel):
    method: str
    params: dict


class ElicitationResponse(BaseModel):
    action: str
    content: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


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
    attachments: Optional[List[str]] = None,
    ctx: Context = None,
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
        ctx (Context, optional): Context object to use. Defaults to None.

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
        if ctx is None:
            return EmailResult(
                success=False,
                message="Credentials missing and context not available.",
                to_email=to_email,
                subject=subject,
                from_email=str(sender),
            )

        # Pause the tool and ask the client (CLI) to prompt the user
        response = await ctx.session.send_request(
            CustomRequest(
                method="elicitation/create",
                params={
                    "mode": "form",
                    "message": "Please provide your SMTP credentials to send this email.",
                    "requestedSchema": {
                        "type": "object",
                        "properties": {
                            "smtp_username": {
                                "type": "string",
                                "title": "SMTP Username (Email)",
                            },
                            "smtp_password": {
                                "type": "string",
                                "title": "SMTP App Password",
                            },
                        },
                        "required": ["smtp_username", "smtp_password"],
                    },
                },
            ),
            ElicitationResponse,
        )

        # 2. Check what the user submitted (using dot notation for Pydantic objects)
        if response and response.action == "accept" and response.content:
            username = response.content.get("smtp_username")
            password = response.content.get("smtp_password")
            sender = from_email or username
        else:
            return EmailResult(
                success=False,
                message="User declined to provide credentials.",
                from_email=str(sender),
                to_email=to_email,
                subject=subject,
                error=response.reason
                if response and response.reason
                else "Action cancelled by user.",
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
                            f'attachment; filename="{os.path.basename(file_path)}"',
                        )
                        message.attach(part)
                else:
                    return EmailResult(
                        success=False,
                        message=f"Attachment not found: {file_path}",
                        from_email=sender,
                        to_email=to_email,
                        subject=subject,
                        error="File does not exist",
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
            subject=subject,
        )

    except smtplib.SMTPAuthenticationError:
        return EmailResult(
            success=False,
            message="Authentication failed",
            from_email=sender,
            to_email=to_email,
            subject=subject,
            error="Check your username and password. For Gmail, use an App Password.",
        )

    except Exception as e:
        return EmailResult(
            success=False,
            message="Failed to send email",
            from_email=sender,
            to_email=to_email,
            subject=subject,
            error=f"{type(e).__name__}: {str(e)}",
        )


@mcp.tool()
async def get_inbox_emails(
    max_emails: int = 10,
    imap_username: Optional[str] = None,
    imap_password: Optional[str] = None,
    imap_server: Optional[str] = None,
    imap_port: Optional[int] = None,
    unread_only: bool = False,
) -> Dict[str, Any]:
    """
    Retrieve emails from the inbox using IMAP.

    Args:
        max_emails (int): Maximum number of emails to retrieve. Default is 10.
        imap_username (str, optional): IMAP login username. Defaults to environment variable SMTP_USERNAME.
        imap_password (str, optional): IMAP login password. Defaults to environment variable SMTP_PASSWORD.
        imap_server (str, optional): IMAP server hostname. Defaults to environment variable IMAP_SERVER or "imap.gmail.com".
        imap_port (int, optional): IMAP server port. Defaults to environment variable IMAP_PORT or 993.
        unread_only (bool): If True, only retrieve unread emails. Default is False.

    Returns:
        Dict with:
            - success (bool): True if operation succeeded.
            - message (str): Human-readable message.
            - emails (List[EmailMessage]): List of email messages.
            - count (int): Number of emails retrieved.
            - error (str, optional): Error message if failed.
    """
    username = imap_username or DEFAULT_SMTP_USERNAME
    password = imap_password or DEFAULT_SMTP_PASSWORD
    server = imap_server or DEFAULT_IMAP_SERVER
    port = imap_port or DEFAULT_IMAP_PORT

    if not username or not password:
        return {
            "success": False,
            "message": "IMAP credentials not provided",
            "emails": [],
            "count": 0,
            "error": "Missing SMTP_USERNAME or SMTP_PASSWORD in environment or parameters",
        }

    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        mail.select("INBOX")

        # Search for emails
        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, message_ids = mail.search(None, search_criteria)

        if status != "OK":
            return {
                "success": False,
                "message": "Failed to search inbox",
                "emails": [],
                "count": 0,
                "error": "IMAP search command failed",
            }

        # Get list of email IDs
        email_ids = message_ids[0].split()
        email_ids.reverse()  # Most recent first
        email_ids = email_ids[:max_emails]

        emails = []
        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, "(RFC822 FLAGS)")
                if status != "OK":
                    continue

                # Parse email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract flags to check if read
                flags = (
                    msg_data[0][0].decode()
                    if isinstance(msg_data[0][0], bytes)
                    else str(msg_data[0][0])
                )
                is_read = "\\Seen" in flags

                # Parse email details
                subject = decode_mime_header(msg.get("Subject", ""))
                from_email = decode_mime_header(msg.get("From", ""))
                to_email = decode_mime_header(msg.get("To", ""))
                date = msg.get("Date", "")

                # Extract body
                body = extract_email_body(msg)

                # Check for attachments
                has_attachments = False
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            has_attachments = True
                            break

                emails.append(
                    EmailMessage(
                        id=email_id.decode(),
                        subject=subject,
                        from_email=from_email,
                        to_email=to_email,
                        date=date,
                        body=body[:500] + "..."
                        if len(body) > 500
                        else body,  # Truncate long bodies
                        has_attachments=has_attachments,
                        is_read=is_read,
                    )
                )
            except Exception:
                # Skip this email if there's an error parsing it
                continue

        mail.close()
        mail.logout()

        return {
            "success": True,
            "message": f"Retrieved {len(emails)} email(s) from inbox",
            "emails": [vars(e) for e in emails],
            "count": len(emails),
        }

    except imaplib.IMAP4.error as e:
        return {
            "success": False,
            "message": "IMAP authentication or connection failed",
            "emails": [],
            "count": 0,
            "error": f"Check your credentials. For Gmail, use an App Password. Error: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": "Failed to retrieve emails",
            "emails": [],
            "count": 0,
            "error": f"{type(e).__name__}: {str(e)}",
        }


@mcp.tool()
async def get_sent_emails(
    max_emails: int = 10,
    imap_username: Optional[str] = None,
    imap_password: Optional[str] = None,
    imap_server: Optional[str] = None,
    imap_port: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve sent emails using IMAP.

    Args:
        max_emails (int): Maximum number of emails to retrieve. Default is 10.
        imap_username (str, optional): IMAP login username. Defaults to environment variable SMTP_USERNAME.
        imap_password (str, optional): IMAP login password. Defaults to environment variable SMTP_PASSWORD.
        imap_server (str, optional): IMAP server hostname. Defaults to environment variable IMAP_SERVER or "imap.gmail.com".
        imap_port (int, optional): IMAP server port. Defaults to environment variable IMAP_PORT or 993.

    Returns:
        Dict with:
            - success (bool): True if operation succeeded.
            - message (str): Human-readable message.
            - emails (List[EmailMessage]): List of sent email messages.
            - count (int): Number of emails retrieved.
            - error (str, optional): Error message if failed.
    """
    username = imap_username or DEFAULT_SMTP_USERNAME
    password = imap_password or DEFAULT_SMTP_PASSWORD
    server = imap_server or DEFAULT_IMAP_SERVER
    port = imap_port or DEFAULT_IMAP_PORT

    if not username or not password:
        return {
            "success": False,
            "message": "IMAP credentials not provided",
            "emails": [],
            "count": 0,
            "error": "Missing SMTP_USERNAME or SMTP_PASSWORD in environment or parameters",
        }

    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)

        # Try different sent folder names (Gmail uses "[Gmail]/Sent Mail")
        sent_folders = ['"[Gmail]/Sent Mail"', "Sent", '"Sent Items"', "INBOX.Sent"]
        folder_selected = False

        for folder in sent_folders:
            try:
                status, _ = mail.select(folder)
                if status == "OK":
                    folder_selected = True
                    break
            except Exception:
                continue

        if not folder_selected:
            return {
                "success": False,
                "message": "Could not find sent folder",
                "emails": [],
                "count": 0,
                "error": "Sent folder not found. Tried: " + ", ".join(sent_folders),
            }

        # Search for all emails in sent folder
        status, message_ids = mail.search(None, "ALL")

        if status != "OK":
            return {
                "success": False,
                "message": "Failed to search sent folder",
                "emails": [],
                "count": 0,
                "error": "IMAP search command failed",
            }

        # Get list of email IDs
        email_ids = message_ids[0].split()
        email_ids.reverse()  # Most recent first
        email_ids = email_ids[:max_emails]

        emails = []
        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                # Parse email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Parse email details
                subject = decode_mime_header(msg.get("Subject", ""))
                from_email = decode_mime_header(msg.get("From", ""))
                to_email = decode_mime_header(msg.get("To", ""))
                date = msg.get("Date", "")

                # Extract body
                body = extract_email_body(msg)

                # Check for attachments
                has_attachments = False
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            has_attachments = True
                            break

                emails.append(
                    EmailMessage(
                        id=email_id.decode(),
                        subject=subject,
                        from_email=from_email,
                        to_email=to_email,
                        date=date,
                        body=body[:500] + "..."
                        if len(body) > 500
                        else body,  # Truncate long bodies
                        has_attachments=has_attachments,
                        is_read=True,  # Sent emails are always "read"
                    )
                )
            except Exception:
                # Skip this email if there's an error parsing it
                continue

        mail.close()
        mail.logout()

        return {
            "success": True,
            "message": f"Retrieved {len(emails)} sent email(s)",
            "emails": [vars(e) for e in emails],
            "count": len(emails),
        }

    except imaplib.IMAP4.error as e:
        return {
            "success": False,
            "message": "IMAP authentication or connection failed",
            "emails": [],
            "count": 0,
            "error": f"Check your credentials. For Gmail, use an App Password. Error: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": "Failed to retrieve sent emails",
            "emails": [],
            "count": 0,
            "error": f"{type(e).__name__}: {str(e)}",
        }


@mcp.tool()
async def download_email_attachments(
    email_id: str,
    download_dir: str = "./attachments",
    imap_username: Optional[str] = None,
    imap_password: Optional[str] = None,
    imap_server: Optional[str] = None,
    imap_port: Optional[int] = None,
    folder: str = "INBOX",
) -> Dict[str, Any]:
    """
    Download all attachments from a specific email.

    Args:
        email_id (str): The email ID to download attachments from (obtained from get_inbox_emails or get_sent_emails).
        download_dir (str): Directory to save attachments. Default is "./attachments".
        imap_username (str, optional): IMAP login username. Defaults to environment variable SMTP_USERNAME.
        imap_password (str, optional): IMAP login password. Defaults to environment variable SMTP_PASSWORD.
        imap_server (str, optional): IMAP server hostname. Defaults to environment variable IMAP_SERVER or "imap.gmail.com".
        imap_port (int, optional): IMAP server port. Defaults to environment variable IMAP_PORT or 993.
        folder (str): Email folder to search in. Default is "INBOX". For sent emails, use "[Gmail]/Sent Mail" for Gmail.

    Returns:
        Dict with:
            - success (bool): True if operation succeeded.
            - message (str): Human-readable message.
            - attachments (List[Dict]): List of downloaded attachments with filename, filepath, and size.
            - count (int): Number of attachments downloaded.
            - error (str, optional): Error message if failed.
    """
    username = imap_username or DEFAULT_SMTP_USERNAME
    password = imap_password or DEFAULT_SMTP_PASSWORD
    server = imap_server or DEFAULT_IMAP_SERVER
    port = imap_port or DEFAULT_IMAP_PORT

    if not username or not password:
        return {
            "success": False,
            "message": "IMAP credentials not provided",
            "attachments": [],
            "count": 0,
            "error": "Missing SMTP_USERNAME or SMTP_PASSWORD in environment or parameters",
        }

    try:
        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)

        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)

        # Select the appropriate folder
        if "[" in folder or "/" in folder:
            folder = f'"{folder}"' if not folder.startswith('"') else folder
        status, _ = mail.select(folder)
        if status != "OK":
            return {
                "success": False,
                "message": f"Could not select folder: {folder}",
                "attachments": [],
                "count": 0,
                "error": f"Failed to select folder '{folder}'",
            }

        # Fetch the email
        status, msg_data = mail.fetch(
            email_id.encode() if isinstance(email_id, str) else email_id, "(RFC822)"
        )

        if status != "OK":
            return {
                "success": False,
                "message": f"Email with ID {email_id} not found",
                "attachments": [],
                "count": 0,
                "error": "Failed to fetch email",
            }

        # Parse email
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Extract attachments
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                # Get content disposition
                content_disposition = part.get("Content-Disposition", "")

                if "attachment" in content_disposition:
                    # Get filename
                    filename = part.get_filename()

                    if filename:
                        # Decode filename if it's encoded
                        filename = decode_mime_header(filename)

                        # Create safe filename (remove any path separators)
                        filename = os.path.basename(filename)

                        # Full filepath
                        filepath = os.path.join(download_dir, filename)

                        # Handle duplicate filenames
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(filepath):
                            filename = f"{base}_{counter}{ext}"
                            filepath = os.path.join(download_dir, filename)
                            counter += 1

                        # Get attachment data
                        attachment_data = part.get_payload(decode=True)

                        if attachment_data:
                            # Write to file
                            with open(filepath, "wb") as f:
                                f.write(attachment_data)

                            file_size = len(attachment_data)
                            attachments.append(
                                {
                                    "filename": filename,
                                    "filepath": filepath,
                                    "size_bytes": file_size,
                                    "size_readable": f"{file_size / 1024:.2f} KB"
                                    if file_size < 1024 * 1024
                                    else f"{file_size / (1024 * 1024):.2f} MB",
                                }
                            )

        mail.close()
        mail.logout()

        if len(attachments) == 0:
            return {
                "success": True,
                "message": "No attachments found in this email",
                "attachments": [],
                "count": 0,
            }

        return {
            "success": True,
            "message": f"Downloaded {len(attachments)} attachment(s) to {download_dir}",
            "attachments": attachments,
            "count": len(attachments),
        }

    except imaplib.IMAP4.error as e:
        return {
            "success": False,
            "message": "IMAP authentication or connection failed",
            "attachments": [],
            "count": 0,
            "error": f"Check your credentials. For Gmail, use an App Password. Error: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": "Failed to download attachments",
            "attachments": [],
            "count": 0,
            "error": f"{type(e).__name__}: {str(e)}",
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
