"""
Email sender module with SMTP support and rate limiting
"""

import asyncio
import logging
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Union
from collections import deque

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import (
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailResult,
    EmailStatus,
)
from .settings import MailSettings, SMTPAccountSettings, settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for email sending."""

    def __init__(
        self,
        max_per_hour: int = 100,
        max_per_minute: Optional[int] = None,
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_per_hour: Maximum emails per hour
            max_per_minute: Maximum emails per minute (optional)
        """
        self.max_per_hour = max_per_hour
        self.max_per_minute = max_per_minute
        
        # Track timestamps of sent emails
        self.hourly_timestamps: deque = deque()
        self.minute_timestamps: deque = deque()
        
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to send an email.
        Blocks until rate limit allows sending.
        """
        async with self._lock:
            now = datetime.utcnow()
            
            # Clean up old timestamps
            self._cleanup_timestamps(now)
            
            # Check hourly limit
            while len(self.hourly_timestamps) >= self.max_per_hour:
                # Wait until oldest timestamp expires
                oldest = self.hourly_timestamps[0]
                wait_until = oldest + timedelta(hours=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(
                        f"Rate limit reached ({self.max_per_hour}/hour). "
                        f"Waiting {wait_seconds:.1f} seconds..."
                    )
                    await asyncio.sleep(wait_seconds)
                    now = datetime.utcnow()
                    self._cleanup_timestamps(now)
                else:
                    break
            
            # Check minute limit if configured
            if self.max_per_minute:
                while len(self.minute_timestamps) >= self.max_per_minute:
                    oldest = self.minute_timestamps[0]
                    wait_until = oldest + timedelta(minutes=1)
                    wait_seconds = (wait_until - now).total_seconds()
                    
                    if wait_seconds > 0:
                        logger.info(
                            f"Rate limit reached ({self.max_per_minute}/minute). "
                            f"Waiting {wait_seconds:.1f} seconds..."
                        )
                        await asyncio.sleep(wait_seconds)
                        now = datetime.utcnow()
                        self._cleanup_timestamps(now)
                    else:
                        break
            
            # Record this send
            self.hourly_timestamps.append(now)
            if self.max_per_minute:
                self.minute_timestamps.append(now)

    def _cleanup_timestamps(self, now: datetime) -> None:
        """Remove timestamps older than the rate limit window."""
        # Clean hourly
        hour_ago = now - timedelta(hours=1)
        while self.hourly_timestamps and self.hourly_timestamps[0] < hour_ago:
            self.hourly_timestamps.popleft()
        
        # Clean minute
        if self.max_per_minute:
            minute_ago = now - timedelta(minutes=1)
            while self.minute_timestamps and self.minute_timestamps[0] < minute_ago:
                self.minute_timestamps.popleft()


class EmailSender:
    """Email sender with SMTP support, templates, and rate limiting."""

    def __init__(self, config: Optional[MailSettings] = None):
        """
        Initialize email sender.
        
        Args:
            config: Mail settings (uses global settings if not provided)
        """
        self.config = config or settings
        
        # Initialize rate limiter if enabled
        if self.config.rate_limit.enabled:
            self.rate_limiter = RateLimiter(
                max_per_hour=self.config.rate_limit.max_emails_per_hour,
                max_per_minute=self.config.rate_limit.max_emails_per_minute,
            )
        else:
            self.rate_limiter = None
        
        # Initialize Jinja2 environment for templates
        if self.config.templates.enabled:
            self.jinja_env = Environment(
                loader=FileSystemLoader(self.config.templates.template_dir),
                autoescape=select_autoescape(["html", "xml"]) if self.config.templates.auto_escape else False,
            )
        else:
            self.jinja_env = None

    async def send_email(
        self,
        email: EmailMessage,
        wait_for_result: bool = True,
    ) -> EmailResult:
        """
        Send an email.
        
        Args:
            email: Email message to send
            wait_for_result: If True, wait for send to complete. If False, returns immediately.
            
        Returns:
            EmailResult with send status
        """
        # Apply rate limiting if enabled
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        try:
            # Get SMTP account configuration
            smtp_account = self.config.get_smtp_account(email.smtp_account)
            
            # Render template if specified
            if email.template_name:
                email = await self._render_template(email)
            
            # Build MIME message
            mime_message = await self._build_mime_message(email, smtp_account)
            
            # Send via SMTP
            message_id = await self._send_smtp(mime_message, email, smtp_account)
            
            return EmailResult(
                status=EmailStatus.SENT,
                message_id=message_id,
                sent_at=datetime.utcnow(),
                smtp_account=email.smtp_account or self.config.default_account,
            )
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return EmailResult(
                status=EmailStatus.FAILED,
                error=str(e),
                smtp_account=email.smtp_account or self.config.default_account,
            )

    async def _render_template(self, email: EmailMessage) -> EmailMessage:
        """Render email template with provided data."""
        if not self.jinja_env:
            raise ValueError("Templates are not enabled in configuration")
        
        if not email.template_name:
            return email
        
        template = self.jinja_env.get_template(email.template_name)
        rendered = template.render(**(email.template_data or {}))
        
        # Determine if template is HTML or plain text
        if email.template_name.endswith(".html"):
            email.html = rendered
        else:
            email.body = rendered
        
        return email

    async def _build_mime_message(
        self,
        email: EmailMessage,
        smtp_account: SMTPAccountSettings,
    ) -> MIMEMultipart:
        """Build MIME message from EmailMessage."""
        # Create message container
        msg = MIMEMultipart("alternative")
        
        # Set headers
        msg["Subject"] = email.subject
        
        # From address
        from_addr = email.from_email or EmailAddress(
            email=smtp_account.from_email,
            name=smtp_account.from_name,
        )
        msg["From"] = str(from_addr)
        
        # To addresses
        to_addrs = [str(addr) if isinstance(addr, EmailAddress) else addr for addr in email.to]
        msg["To"] = ", ".join(to_addrs)
        
        # CC addresses
        if email.cc:
            cc_addrs = [str(addr) if isinstance(addr, EmailAddress) else addr for addr in email.cc]
            msg["Cc"] = ", ".join(cc_addrs)
        
        # Reply-To
        reply_to = email.reply_to or smtp_account.reply_to
        if reply_to:
            msg["Reply-To"] = str(reply_to) if isinstance(reply_to, EmailAddress) else reply_to
        
        # Custom headers
        if email.headers:
            for key, value in email.headers.items():
                msg[key] = value
        
        # Priority
        if email.priority == "high":
            msg["X-Priority"] = "1"
            msg["Importance"] = "high"
        elif email.priority == "low":
            msg["X-Priority"] = "5"
            msg["Importance"] = "low"
        
        # Add body parts
        if email.body:
            msg.attach(MIMEText(email.body, "plain", "utf-8"))
        
        if email.html:
            msg.attach(MIMEText(email.html, "html", "utf-8"))
        
        # Add attachments
        if email.attachments:
            for attachment in email.attachments:
                part = MIMEApplication(attachment.content, Name=attachment.filename)
                part["Content-Disposition"] = f'attachment; filename="{attachment.filename}"'
                part["Content-Type"] = attachment.content_type
                msg.attach(part)
        
        return msg

    async def _send_smtp(
        self,
        message: MIMEMultipart,
        email: EmailMessage,
        smtp_account: SMTPAccountSettings,
    ) -> str:
        """Send email via SMTP."""
        # Import SMTPSecurity enum for comparison
        from .settings import SMTPSecurity
        
        # Determine TLS settings
        use_tls = smtp_account.security == SMTPSecurity.TLS
        start_tls = smtp_account.security == SMTPSecurity.STARTTLS
        
        # Create SMTP client
        smtp = aiosmtplib.SMTP(
            hostname=smtp_account.host,
            port=smtp_account.port,
            use_tls=use_tls,
            timeout=smtp_account.timeout,
        )
        
        try:
            # Connect
            await smtp.connect()
            
            # STARTTLS if needed (only for starttls mode, not for tls mode)
            # When use_tls=True, connection is already encrypted, don't call starttls()
            if start_tls and not use_tls:
                await smtp.starttls()
            
            # Login
            await smtp.login(smtp_account.username, smtp_account.password)
            
            # Get all recipients
            recipients = [
                addr if isinstance(addr, str) else addr.email
                for addr in email.to
            ]
            if email.cc:
                recipients.extend([
                    addr if isinstance(addr, str) else addr.email
                    for addr in email.cc
                ])
            if email.bcc:
                recipients.extend([
                    addr if isinstance(addr, str) else addr.email
                    for addr in email.bcc
                ])
            
            # Send
            response = await smtp.send_message(message, recipients=recipients)
            
            # Extract message ID from response
            message_id = message.get("Message-ID", "unknown")
            
            logger.info(f"Email sent successfully to {len(recipients)} recipients")
            
            return message_id
            
        finally:
            # Always close connection
            try:
                await smtp.quit()
            except Exception:
                pass
