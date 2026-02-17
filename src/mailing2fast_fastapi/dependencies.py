"""
FastAPI dependencies for email functionality
"""

from typing import Optional

from fastapi import Depends

from .manager import MailManager, get_manager
from .queue import EmailQueue
from .sender import EmailSender
from .settings import MailSettings, settings
from .worker import EmailWorker

# Global instances (singletons)
_queue: Optional[EmailQueue] = None
_worker: Optional[EmailWorker] = None


def get_mail_manager(config: MailSettings = Depends(lambda: settings)) -> MailManager:
    """
    FastAPI dependency for MailManager.
    
    Returns singleton instance.
    
    Usage:
        @app.get("/accounts")
        async def list_accounts(manager: MailManager = Depends(get_mail_manager)):
            return {"accounts": manager.list_accounts()}
    """
    return get_manager(config)


def get_email_sender(
    account_name: Optional[str] = None,
    manager: MailManager = Depends(get_mail_manager)
) -> EmailSender:
    """
    FastAPI dependency for EmailSender.
    
    Returns sender for specified account (or default if not specified).
    
    Args:
        account_name: Name of the SMTP account to use. If None, uses default.
        manager: MailManager instance (injected).
    
    Usage:
        # Get default sender
        @app.post("/send")
        async def send_email(sender: EmailSender = Depends(get_email_sender)):
            ...
        
        # Get specific account sender
        from functools import partial
        
        get_support_sender = partial(get_email_sender, account_name="support")
        
        @app.post("/send-support")
        async def send_support_email(sender: EmailSender = Depends(get_support_sender)):
            ...
    """
    return manager.get_sender(account_name)


async def get_email_queue(config: MailSettings = Depends(lambda: settings)) -> EmailQueue:
    """
    FastAPI dependency for EmailQueue.
    
    Returns singleton instance and ensures connection.
    """
    global _queue
    if _queue is None:
        _queue = EmailQueue(config)
    
    # Ensure connected
    await _queue.connect()
    
    return _queue


async def get_email_worker(
    config: MailSettings = Depends(lambda: settings),
    manager: MailManager = Depends(get_mail_manager),
    queue: EmailQueue = Depends(get_email_queue),
) -> EmailWorker:
    """
    FastAPI dependency for EmailWorker.
    
    Returns singleton instance.
    """
    global _worker
    if _worker is None:
        # Get default sender from manager
        sender = manager.get_sender()
        _worker = EmailWorker(config, sender, queue)
    return _worker


async def startup_email_worker(config: Optional[MailSettings] = None) -> EmailWorker:
    """
    Start email worker on application startup.
    
    Usage in FastAPI:
        @app.on_event("startup")
        async def startup():
            await startup_email_worker()
    
    Args:
        config: Mail settings (uses global settings if not provided)
        
    Returns:
        Started EmailWorker instance
    """
    global _worker, _queue
    
    cfg = config or settings
    
    # Get manager and default sender
    manager = get_manager(cfg)
    sender = manager.get_sender()
    
    # Create queue if not exists
    if _queue is None:
        _queue = EmailQueue(cfg)
    
    # Create worker if not exists
    if _worker is None:
        _worker = EmailWorker(cfg, sender, _queue)
    
    # Start worker
    print("📧 Starting email worker...")
    await _worker.start()
    
    # Print configured accounts
    accounts = manager.list_accounts()
    default = manager.get_default_account()
    print(f"  ✅ Configured accounts: {', '.join(accounts)}")
    print(f"  ✅ Default account: {default}")
    
    return _worker


async def shutdown_email_worker() -> None:
    """
    Stop email worker on application shutdown.
    
    Usage in FastAPI:
        @app.on_event("shutdown")
        async def shutdown():
            await shutdown_email_worker()
    """
    global _worker
    
    if _worker is not None:
        print("📧 Stopping email worker...")
        await _worker.stop()
        print("  ✅ Email worker stopped")
