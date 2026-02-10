"""
Basic tests for email sender
"""

import pytest
from mailing2fast_fastapi import EmailMessage, EmailSender, EmailStatus


@pytest.mark.asyncio
async def test_email_message_validation():
    """Test email message validation."""
    # Valid email
    email = EmailMessage(
        to=["test@example.com"],
        subject="Test",
        body="Test body",
    )
    assert email.to == ["test@example.com"]
    assert email.subject == "Test"
    
    # Should fail without body or html
    with pytest.raises(ValueError):
        EmailMessage(
            to=["test@example.com"],
            subject="Test",
        )


@pytest.mark.asyncio
async def test_email_sender_initialization():
    """Test email sender can be initialized."""
    sender = EmailSender()
    assert sender is not None
    assert sender.config is not None


# Add more tests as needed
# Note: Full integration tests require a running SMTP server and Redis
