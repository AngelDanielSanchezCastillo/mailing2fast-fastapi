"""
FastAPI integration example
"""

from fastapi import Depends, FastAPI
from pydantic import BaseModel, EmailStr

from mailing2fast_fastapi import (
    EmailMessage,
    EmailQueue,
    EmailResult,
    EmailSender,
    get_email_queue,
    get_email_sender,
    get_email_worker,
    shutdown_email_worker,
    startup_email_worker,
)

# Create FastAPI app
app = FastAPI(
    title="Mailing2Fast Example API",
    description="Example API demonstrating mailing2fast-fastapi integration",
)


# Lifecycle events
@app.on_event("startup")
async def startup():
    """Start email worker on app startup."""
    print("🚀 Starting email worker...")
    await startup_email_worker()
    print("✅ Email worker started")


@app.on_event("shutdown")
async def shutdown():
    """Stop email worker on app shutdown."""
    print("🛑 Stopping email worker...")
    await shutdown_email_worker()
    print("✅ Email worker stopped")


# Request models
class SendEmailRequest(BaseModel):
    """Request model for sending email."""

    to: list[EmailStr]
    subject: str
    body: str
    html: str | None = None
    smtp_account: str | None = None


class QueueEmailRequest(BaseModel):
    """Request model for queueing email."""

    to: list[EmailStr]
    subject: str
    body: str
    html: str | None = None
    smtp_account: str | None = None
    priority: bool = False


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Mailing2Fast FastAPI Example",
        "endpoints": {
            "send_email": "/send-email",
            "queue_email": "/queue-email",
            "queue_stats": "/queue/stats",
        },
    }


@app.post("/send-email", response_model=dict)
async def send_email(
    request: SendEmailRequest,
    sender: EmailSender = Depends(get_email_sender),
):
    """
    Send email synchronously and wait for result.
    
    This endpoint will wait for the email to be sent before returning.
    """
    email = EmailMessage(
        to=request.to,
        subject=request.subject,
        body=request.body,
        html=request.html,
        smtp_account=request.smtp_account,
    )
    
    result = await sender.send_email(email)
    
    return {
        "status": result.status.value,
        "message_id": result.message_id,
        "sent_at": result.sent_at.isoformat() if result.sent_at else None,
        "error": result.error,
    }


@app.post("/queue-email", response_model=dict)
async def queue_email(
    request: QueueEmailRequest,
    queue: EmailQueue = Depends(get_email_queue),
):
    """
    Queue email for async processing.
    
    This endpoint returns immediately after queueing the email.
    The background worker will process it.
    """
    email = EmailMessage(
        to=request.to,
        subject=request.subject,
        body=request.body,
        html=request.html,
        smtp_account=request.smtp_account,
    )
    
    await queue.enqueue(email, priority=request.priority)
    
    return {
        "status": "queued",
        "priority": request.priority,
    }


@app.get("/queue/stats")
async def get_queue_stats(queue: EmailQueue = Depends(get_email_queue)):
    """Get queue statistics."""
    return {
        "main_queue": await queue.get_queue_size(),
        "retry_queue": await queue.get_retry_queue_size(),
        "dead_letter_queue": await queue.get_dlq_size(),
    }


@app.post("/queue/clear")
async def clear_queues(queue: EmailQueue = Depends(get_email_queue)):
    """Clear all queues (use with caution!)."""
    await queue.clear_queue()
    await queue.clear_retry_queue()
    
    return {"status": "cleared"}


# Example: Send welcome email
@app.post("/users/{user_id}/welcome")
async def send_welcome_email(
    user_id: int,
    email: EmailStr,
    queue: EmailQueue = Depends(get_email_queue),
):
    """Send welcome email to new user (queued)."""
    welcome_email = EmailMessage(
        to=[email],
        subject="Welcome to Our Service!",
        html=f"""
        <html>
            <body>
                <h1>Welcome!</h1>
                <p>Thank you for joining our service.</p>
                <p>Your user ID is: {user_id}</p>
            </body>
        </html>
        """,
        smtp_account="support",  # Use support account
    )
    
    await queue.enqueue(welcome_email)
    
    return {"status": "welcome_email_queued", "user_id": user_id}


# Example: Send transaction confirmation
@app.post("/transactions/{transaction_id}/confirm")
async def send_transaction_confirmation(
    transaction_id: str,
    email: EmailStr,
    amount: float,
    sender: EmailSender = Depends(get_email_sender),
):
    """Send transaction confirmation (synchronous)."""
    confirmation_email = EmailMessage(
        to=[email],
        subject=f"Transaction Confirmation - {transaction_id}",
        html=f"""
        <html>
            <body>
                <h1>Transaction Confirmed</h1>
                <p>Your transaction has been processed successfully.</p>
                <ul>
                    <li>Transaction ID: {transaction_id}</li>
                    <li>Amount: ${amount:.2f}</li>
                </ul>
            </body>
        </html>
        """,
        smtp_account="transactions",  # Use transactions account
        priority="high",
    )
    
    result = await sender.send_email(confirmation_email)
    
    return {
        "status": result.status.value,
        "transaction_id": transaction_id,
        "email_sent": result.is_success(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
