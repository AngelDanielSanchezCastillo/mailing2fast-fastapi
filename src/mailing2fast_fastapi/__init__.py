"""
mailing2fast-fastapi - Simple and fast mailing module for FastAPI

A comprehensive email module for FastAPI with async support, Redis queue management,
and Pydantic settings configuration.

Features:
- Multiple SMTP account support
- Async email sending with rate limiting
- Redis-based FIFO queue with retry logic
- Jinja2 template support
- Background worker for queue processing
- FastAPI integration with dependencies
"""

from .__version__ import __version__
from .dependencies import (
    get_email_queue,
    get_email_sender,
    get_email_worker,
    shutdown_email_worker,
    startup_email_worker,
)
from .models import (
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailResult,
    EmailStatus,
    QueuedEmail,
)
from .queue import EmailQueue
from .sender import EmailSender
from .settings import (
    EmailPriority,
    MailSettings,
    QueueSettings,
    RateLimitSettings,
    RedisSettings,
    SMTPAccountSettings,
    SMTPSecurity,
    TemplateSettings,
    settings,
)
from .worker import EmailWorker, run_worker

__all__ = [
    # Version
    "__version__",
    # Main classes
    "EmailSender",
    "EmailQueue",
    "EmailWorker",
    # Models
    "EmailMessage",
    "EmailAddress",
    "EmailAttachment",
    "EmailResult",
    "EmailStatus",
    "QueuedEmail",
    # Settings
    "MailSettings",
    "SMTPAccountSettings",
    "RedisSettings",
    "QueueSettings",
    "RateLimitSettings",
    "TemplateSettings",
    "SMTPSecurity",
    "EmailPriority",
    "settings",
    # FastAPI dependencies
    "get_email_sender",
    "get_email_queue",
    "get_email_worker",
    "startup_email_worker",
    "shutdown_email_worker",
    # Worker utilities
    "run_worker",
]
