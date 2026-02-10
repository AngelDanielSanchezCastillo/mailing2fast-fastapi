"""
Settings module for mailing2fast-fastapi
Handles configuration using Pydantic Settings with environment variables
"""

import os
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in the current working directory (where the app is running)
DOTENV_PATH = os.path.join(os.getcwd(), ".env")


class EmailPriority(str, Enum):
    """Email priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class SMTPSecurity(str, Enum):
    """SMTP security protocols."""

    NONE = "none"
    TLS = "tls"
    STARTTLS = "starttls"


class SMTPAccountSettings(BaseModel):
    """Configuration for a single SMTP account."""

    host: str = Field(..., description="SMTP server host")
    port: int = Field(default=587, description="SMTP server port")
    username: str = Field(..., description="SMTP username")
    password: str = Field(..., description="SMTP password")
    security: SMTPSecurity = Field(
        default=SMTPSecurity.STARTTLS, description="Security protocol (none, tls, starttls)"
    )
    timeout: int = Field(default=60, description="Connection timeout in seconds")
    
    # Default sender information for this account
    from_email: str = Field(..., description="Default sender email address")
    from_name: Optional[str] = Field(default=None, description="Default sender name")
    reply_to: Optional[str] = Field(default=None, description="Default reply-to address")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class RedisSettings(BaseModel):
    """Configuration for Redis connection."""

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")
    queue_name: str = Field(default="mailing2fast:queue", description="Queue name for emails")
    retry_queue_name: str = Field(
        default="mailing2fast:retry", description="Queue name for retry emails"
    )
    dead_letter_queue_name: str = Field(
        default="mailing2fast:dlq", description="Dead letter queue name"
    )
    max_connections: int = Field(default=10, description="Maximum Redis connections in pool")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("db")
    @classmethod
    def validate_db(cls, v: int) -> int:
        """Validate Redis database number."""
        if not 0 <= v <= 15:
            raise ValueError("Redis database must be between 0 and 15")
        return v


class QueueSettings(BaseModel):
    """Configuration for email queue processing."""

    enabled: bool = Field(default=True, description="Enable queue processing")
    max_retries: int = Field(default=3, description="Maximum retry attempts for failed emails")
    retry_delay: int = Field(
        default=300, description="Delay in seconds before retrying failed email"
    )
    worker_poll_interval: int = Field(
        default=1, description="Worker polling interval in seconds"
    )
    batch_size: int = Field(
        default=10, description="Number of emails to process in one batch"
    )


class RateLimitSettings(BaseModel):
    """Configuration for rate limiting email sending."""

    enabled: bool = Field(default=True, description="Enable rate limiting")
    max_emails_per_hour: int = Field(
        default=100, description="Maximum emails to send per hour"
    )
    max_emails_per_minute: Optional[int] = Field(
        default=None, description="Maximum emails to send per minute (optional)"
    )

    @field_validator("max_emails_per_hour")
    @classmethod
    def validate_max_per_hour(cls, v: int) -> int:
        """Validate max emails per hour is positive."""
        if v <= 0:
            raise ValueError("max_emails_per_hour must be greater than 0")
        return v

    @field_validator("max_emails_per_minute")
    @classmethod
    def validate_max_per_minute(cls, v: Optional[int]) -> Optional[int]:
        """Validate max emails per minute is positive if set."""
        if v is not None and v <= 0:
            raise ValueError("max_emails_per_minute must be greater than 0")
        return v


class TemplateSettings(BaseModel):
    """Configuration for email templates."""

    enabled: bool = Field(default=True, description="Enable template support")
    template_dir: str = Field(
        default="templates/emails", description="Directory for email templates"
    )
    auto_escape: bool = Field(
        default=True, description="Auto-escape HTML in templates for security"
    )


class MailSettings(BaseSettings):
    """Main mailing configuration."""

    # SMTP Accounts - Support for multiple named accounts
    smtp_accounts: Dict[str, SMTPAccountSettings] = Field(
        default_factory=dict,
        description="Dictionary of named SMTP accounts (e.g., 'support', 'transactions')",
    )
    
    # Default account to use when none is specified
    default_account: str = Field(
        default="default", description="Name of default SMTP account to use"
    )

    # Redis configuration
    redis: RedisSettings = Field(
        default_factory=RedisSettings, description="Redis configuration"
    )

    # Queue configuration
    queue: QueueSettings = Field(
        default_factory=QueueSettings, description="Queue processing configuration"
    )

    # Rate limiting
    rate_limit: RateLimitSettings = Field(
        default_factory=RateLimitSettings, description="Rate limiting configuration"
    )

    # Template configuration
    templates: TemplateSettings = Field(
        default_factory=TemplateSettings, description="Template configuration"
    )

    # General settings
    async_send_timeout: int = Field(
        default=30, description="Timeout for async email sending in seconds"
    )
    
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_prefix="MAIL_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    def get_smtp_account(self, account_name: Optional[str] = None) -> SMTPAccountSettings:
        """
        Get SMTP account configuration by name.
        
        Args:
            account_name: Name of the account. If None, uses default_account.
            
        Returns:
            SMTPAccountSettings for the requested account.
            
        Raises:
            ValueError: If account doesn't exist.
        """
        name = account_name or self.default_account
        
        if name not in self.smtp_accounts:
            available = ", ".join(self.smtp_accounts.keys())
            raise ValueError(
                f"SMTP account '{name}' not found. Available accounts: {available}"
            )
        
        return self.smtp_accounts[name]

    def has_account(self, account_name: str) -> bool:
        """Check if an SMTP account exists."""
        return account_name in self.smtp_accounts


# Initialize settings with error handling
try:
    settings = MailSettings()
    
    # Validate that at least one SMTP account is configured
    if not settings.smtp_accounts:
        print("⚠️  Warning: No SMTP accounts configured. Please add at least one account.")
        print("   Example: MAIL_SMTP_ACCOUNTS__DEFAULT__HOST=smtp.gmail.com")
        
except Exception as e:
    import traceback

    print("🚨 Error loading mail configuration:")
    print(e)
    traceback.print_exc()
    
    # Fallback to minimal configuration
    settings = MailSettings()
    print("⚠️  Using fallback mail configuration (no SMTP accounts)")
