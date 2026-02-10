# mailing2fast-fastapi

🚀 Simple and fast mailing module for FastAPI with async support and Redis queue management

> [!WARNING]
> **Internal Use Notice**
> 
> This package is designed and maintained by the **Solautyc Team** for internal use. While it is publicly available, it may not work as expected in all environments or use cases outside of our specific infrastructure. We do not provide support or guarantees for external usage, and we are not responsible for any issues that may arise from using this package in other contexts.
> 
> Use at your own risk. Contributions and feedback are welcome, but compatibility with external environments is not guaranteed.

## Features

- 📧 **Multiple SMTP Accounts**: Configure multiple named email accounts (e.g., "support", "transactions", "notifications")
- ⚡ **Async Email Sending**: Full async/await support with aiosmtplib
- 🔄 **Redis Queue Management**: FIFO queue with automatic retry and dead letter queue
- 🎯 **Two Sending Modes**:
  - **Synchronous**: Send and wait for success/failure response
  - **Async Queue**: Fire-and-forget with background worker processing
- 🚦 **Rate Limiting**: Configurable rate limits (default: 100 emails/hour)
- 📝 **Jinja2 Templates**: Built-in template support for HTML emails
- 📎 **Attachments**: Easy attachment handling
- 🔁 **Automatic Retry**: Exponential backoff for failed emails
- ⚙️ **Pydantic Settings**: Type-safe configuration with environment variables
- 🎨 **FastAPI Integration**: Ready-to-use dependencies and lifecycle hooks

## Installation

### From PyPI (Recommended)

```bash
pip install mailing2fast-fastapi
```

### From Source

```bash
# Clone the repository
git clone https://github.com/AngelDanielSanchezCastillo/mailing2fast-fastapi.git
cd mailing2fast-fastapi

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure Environment Variables

Create a `.env` file:

```bash
# Default SMTP Account
MAIL_SMTP_ACCOUNTS__DEFAULT__HOST=smtp.gmail.com
MAIL_SMTP_ACCOUNTS__DEFAULT__PORT=587
MAIL_SMTP_ACCOUNTS__DEFAULT__USERNAME=your-email@gmail.com
MAIL_SMTP_ACCOUNTS__DEFAULT__PASSWORD=your-app-password
MAIL_SMTP_ACCOUNTS__DEFAULT__FROM_EMAIL=your-email@gmail.com
MAIL_SMTP_ACCOUNTS__DEFAULT__FROM_NAME=Your Name

# Support Account (optional)
MAIL_SMTP_ACCOUNTS__SUPPORT__HOST=smtp.gmail.com
MAIL_SMTP_ACCOUNTS__SUPPORT__PORT=587
MAIL_SMTP_ACCOUNTS__SUPPORT__USERNAME=support@yourcompany.com
MAIL_SMTP_ACCOUNTS__SUPPORT__PASSWORD=support-password
MAIL_SMTP_ACCOUNTS__SUPPORT__FROM_EMAIL=support@yourcompany.com
MAIL_SMTP_ACCOUNTS__SUPPORT__FROM_NAME=Support Team

# Redis Configuration
MAIL_REDIS__HOST=localhost
MAIL_REDIS__PORT=6379
MAIL_REDIS__DB=0

# Rate Limiting (optional)
MAIL_RATE_LIMIT__MAX_EMAILS_PER_HOUR=100
MAIL_RATE_LIMIT__MAX_EMAILS_PER_MINUTE=10
```

### 2. Basic Usage - Synchronous Sending

```python
import asyncio
from mailing2fast_fastapi import EmailSender, EmailMessage

async def main():
    sender = EmailSender()
    
    email = EmailMessage(
        to=["recipient@example.com"],
        subject="Hello from mailing2fast!",
        body="This is a plain text email",
        html="<h1>This is an HTML email</h1>",
    )
    
    result = await sender.send_email(email)
    
    if result.is_success():
        print(f"Email sent! Message ID: {result.message_id}")
    else:
        print(f"Failed to send: {result.error}")

asyncio.run(main())
```

### 3. Async Queue Mode

```python
import asyncio
from mailing2fast_fastapi import EmailQueue, EmailMessage, EmailWorker

async def main():
    # Start background worker
    worker = EmailWorker()
    await worker.start()
    
    # Queue emails (fire-and-forget)
    queue = EmailQueue()
    await queue.connect()
    
    email = EmailMessage(
        to=["recipient@example.com"],
        subject="Queued Email",
        body="This email will be sent by the background worker",
    )
    
    await queue.enqueue(email)
    print("Email queued successfully!")
    
    # Worker will process it in the background
    # Keep worker running...
    await asyncio.sleep(60)
    
    await worker.stop()
    await queue.disconnect()

asyncio.run(main())
```

### 4. FastAPI Integration

```python
from fastapi import FastAPI, Depends
from mailing2fast_fastapi import (
    EmailMessage,
    EmailSender,
    EmailQueue,
    get_email_sender,
    get_email_queue,
    startup_email_worker,
    shutdown_email_worker,
)

app = FastAPI()

# Start/stop worker with app lifecycle
@app.on_event("startup")
async def startup():
    await startup_email_worker()

@app.on_event("shutdown")
async def shutdown():
    await shutdown_email_worker()

# Synchronous sending endpoint
@app.post("/send-email")
async def send_email(sender: EmailSender = Depends(get_email_sender)):
    email = EmailMessage(
        to=["user@example.com"],
        subject="Welcome!",
        html="<h1>Welcome to our service!</h1>",
    )
    
    result = await sender.send_email(email)
    return {"status": result.status, "message_id": result.message_id}

# Async queue endpoint
@app.post("/queue-email")
async def queue_email(queue: EmailQueue = Depends(get_email_queue)):
    email = EmailMessage(
        to=["user@example.com"],
        subject="Newsletter",
        html="<h1>Monthly Newsletter</h1>",
        smtp_account="support",  # Use specific account
    )
    
    await queue.enqueue(email)
    return {"status": "queued"}
```

## Multiple SMTP Accounts

Configure different accounts for different purposes:

```python
email = EmailMessage(
    to=["customer@example.com"],
    subject="Payment Confirmation",
    html="<h1>Payment received!</h1>",
    smtp_account="transactions",  # Use transactions account
)
```

## Templates

Create Jinja2 templates in `templates/emails/`:

**templates/emails/welcome.html:**
```html
<h1>Welcome, {{ name }}!</h1>
<p>Thank you for joining {{ company_name }}.</p>
```

**Usage:**
```python
email = EmailMessage(
    to=["user@example.com"],
    subject="Welcome!",
    template_name="welcome.html",
    template_data={
        "name": "John Doe",
        "company_name": "Acme Corp"
    },
)
```

## Rate Limiting

Rate limiting is enabled by default (100 emails/hour). Configure via environment variables:

```bash
MAIL_RATE_LIMIT__ENABLED=true
MAIL_RATE_LIMIT__MAX_EMAILS_PER_HOUR=100
MAIL_RATE_LIMIT__MAX_EMAILS_PER_MINUTE=10
```

## Queue Management

Monitor queue status:

```python
queue = EmailQueue()
await queue.connect()

stats = {
    "pending": await queue.get_queue_size(),
    "retry": await queue.get_retry_queue_size(),
    "failed": await queue.get_dlq_size(),
}
print(stats)
```

## 📚 Documentation

- **[Usage Guide](docs/usage.md)** - Comprehensive usage guide
- **[Configuration](docs/env.example)** - All configuration options

## Module Structure

```
mailing2fast-fastapi/
├── pyproject.toml
├── MANIFEST.in
├── README.md
├── LICENSE
├── src/
│   └── mailing2fast_fastapi/
│       ├── __init__.py
│       ├── __version__.py
│       ├── settings.py       # Pydantic settings
│       ├── models.py          # Email schemas
│       ├── sender.py          # Email sender
│       ├── queue.py           # Redis queue
│       ├── worker.py          # Background worker
│       └── dependencies.py    # FastAPI deps
├── docs/
│   ├── env.example
│   ├── usage.md
│   └── publishing.md
├── examples/
│   ├── basic_usage.py
│   ├── async_queue.py
│   └── fastapi_integration.py
└── tests/
    ├── test_sender.py
    ├── test_queue.py
    └── test_integration.py
```

## Acknowledgments

This project uses the following open-source packages:

- [FastAPI](https://github.com/tiangolo/fastapi) - Modern web framework (MIT License)
- [Pydantic](https://github.com/pydantic/pydantic) - Data validation (MIT License)
- [Redis](https://github.com/redis/redis-py) - Redis client (MIT License)
- [aiosmtplib](https://github.com/cole/aiosmtplib) - Async SMTP client (MIT License)
- [Jinja2](https://github.com/pallets/jinja) - Template engine (BSD License)

We are grateful to the maintainers and contributors of these projects.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Angel Daniel Sanchez Castillo

**Note**: This package is designed and maintained by the Solautyc Team for internal use. While publicly available under MIT license, use at your own risk.
