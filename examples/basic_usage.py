"""
Basic email sending example
"""

import asyncio

from mailing2fast_fastapi import EmailAddress, EmailMessage, EmailSender


async def main():
    """Send a simple email."""
    # Create sender
    sender = EmailSender()
    
    # Create email message
    email = EmailMessage(
        to=["recipient@example.com"],
        subject="Hello from mailing2fast-fastapi!",
        body="This is a plain text email body.",
        html="<h1>Hello!</h1><p>This is an <strong>HTML</strong> email body.</p>",
    )
    
    # Send email and wait for result
    print("Sending email...")
    result = await sender.send_email(email)
    
    if result.is_success():
        print(f"✅ Email sent successfully!")
        print(f"   Message ID: {result.message_id}")
        print(f"   Sent at: {result.sent_at}")
    else:
        print(f"❌ Failed to send email")
        print(f"   Error: {result.error}")


async def send_with_cc_bcc():
    """Send email with CC and BCC."""
    sender = EmailSender()
    
    email = EmailMessage(
        to=["primary@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        subject="Email with CC and BCC",
        body="This email has CC and BCC recipients.",
    )
    
    result = await sender.send_email(email)
    print(f"Status: {result.status}")


async def send_with_attachments():
    """Send email with attachments."""
    sender = EmailSender()
    
    # Read file content
    with open("document.pdf", "rb") as f:
        pdf_content = f.read()
    
    from mailing2fast_fastapi import EmailAttachment
    
    email = EmailMessage(
        to=["recipient@example.com"],
        subject="Email with Attachment",
        body="Please find the attached document.",
        attachments=[
            EmailAttachment(
                filename="document.pdf",
                content=pdf_content,
                content_type="application/pdf",
            )
        ],
    )
    
    result = await sender.send_email(email)
    print(f"Status: {result.status}")


async def send_with_custom_sender():
    """Send email with custom sender information."""
    sender = EmailSender()
    
    email = EmailMessage(
        to=["recipient@example.com"],
        from_email=EmailAddress(
            email="custom@example.com",
            name="Custom Sender Name",
        ),
        reply_to="reply-to@example.com",
        subject="Email with Custom Sender",
        body="This email has custom sender information.",
    )
    
    result = await sender.send_email(email)
    print(f"Status: {result.status}")


async def send_with_specific_account():
    """Send email using a specific SMTP account."""
    sender = EmailSender()
    
    email = EmailMessage(
        to=["customer@example.com"],
        subject="Support Request Response",
        body="Thank you for contacting support.",
        smtp_account="support",  # Use the 'support' SMTP account
    )
    
    result = await sender.send_email(email)
    print(f"Status: {result.status}")


if __name__ == "__main__":
    # Run the basic example
    asyncio.run(main())
    
    # Uncomment to run other examples:
    # asyncio.run(send_with_cc_bcc())
    # asyncio.run(send_with_attachments())
    # asyncio.run(send_with_custom_sender())
    # asyncio.run(send_with_specific_account())
