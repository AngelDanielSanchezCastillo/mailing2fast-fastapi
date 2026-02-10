"""
Email models and schemas for mailing2fast-fastapi
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmailStatus(str, Enum):
    """Email delivery status."""

    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class EmailAddress(BaseModel):
    """Email address with optional display name."""

    email: EmailStr = Field(..., description="Email address")
    name: Optional[str] = Field(default=None, description="Display name")

    def __str__(self) -> str:
        """Format as 'Name <email@example.com>' or just 'email@example.com'."""
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


class EmailAttachment(BaseModel):
    """Email attachment."""

    filename: str = Field(..., description="Attachment filename")
    content: bytes = Field(..., description="Attachment content as bytes")
    content_type: str = Field(
        default="application/octet-stream", description="MIME content type"
    )


class EmailMessage(BaseModel):
    """Complete email message structure."""

    # Recipients
    to: List[Union[EmailStr, EmailAddress]] = Field(
        ..., description="List of recipient email addresses"
    )
    cc: Optional[List[Union[EmailStr, EmailAddress]]] = Field(
        default=None, description="CC recipients"
    )
    bcc: Optional[List[Union[EmailStr, EmailAddress]]] = Field(
        default=None, description="BCC recipients"
    )

    # Sender (optional - will use account defaults if not provided)
    from_email: Optional[Union[EmailStr, EmailAddress]] = Field(
        default=None, description="Sender email address"
    )
    reply_to: Optional[Union[EmailStr, EmailAddress]] = Field(
        default=None, description="Reply-to address"
    )

    # Content
    subject: str = Field(..., description="Email subject")
    body: Optional[str] = Field(default=None, description="Plain text body")
    html: Optional[str] = Field(default=None, description="HTML body")

    # Attachments
    attachments: Optional[List[EmailAttachment]] = Field(
        default=None, description="Email attachments"
    )

    # Template support
    template_name: Optional[str] = Field(
        default=None, description="Template name (if using templates)"
    )
    template_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Data for template rendering"
    )

    # Metadata
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Custom email headers"
    )
    priority: str = Field(default="normal", description="Email priority (low, normal, high)")

    # Account selection
    smtp_account: Optional[str] = Field(
        default=None, description="SMTP account name to use (uses default if not specified)"
    )

    @field_validator("to", "cc", "bcc")
    @classmethod
    def validate_recipients(
        cls, v: Optional[List[Union[EmailStr, EmailAddress]]]
    ) -> Optional[List[Union[EmailStr, EmailAddress]]]:
        """Ensure at least one recipient exists."""
        if v is not None and len(v) == 0:
            raise ValueError("Recipient list cannot be empty if provided")
        return v

    @field_validator("body", "html")
    @classmethod
    def validate_content(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure at least body or html is provided."""
        # This will be checked in model_validator
        return v

    def model_post_init(self, __context) -> None:
        """Validate that at least body or html is provided."""
        if not self.body and not self.html and not self.template_name:
            raise ValueError(
                "At least one of 'body', 'html', or 'template_name' must be provided"
            )


class EmailResult(BaseModel):
    """Result of email sending operation."""

    status: EmailStatus = Field(..., description="Email delivery status")
    message_id: Optional[str] = Field(default=None, description="Message ID from SMTP server")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    sent_at: Optional[datetime] = Field(default=None, description="Timestamp when sent")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    smtp_account: Optional[str] = Field(
        default=None, description="SMTP account used for sending"
    )

    def is_success(self) -> bool:
        """Check if email was sent successfully."""
        return self.status == EmailStatus.SENT

    def is_failed(self) -> bool:
        """Check if email failed permanently."""
        return self.status == EmailStatus.FAILED


class QueuedEmail(BaseModel):
    """Email in queue with metadata."""

    email: EmailMessage = Field(..., description="Email message")
    queued_at: datetime = Field(
        default_factory=datetime.utcnow, description="When email was queued"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    next_retry_at: Optional[datetime] = Field(
        default=None, description="When to retry next"
    )
