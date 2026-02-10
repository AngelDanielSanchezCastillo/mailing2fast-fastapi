"""
FastAPI dependencies for email functionality
"""

from typing import Optional

from fastapi import Depends

from .queue import EmailQueue
from .sender import EmailSender
from .settings import MailSettings, settings
from .worker import EmailWorker

# Global instances (singletons)
_sender: Optional[EmailSender] = None
_queue: Optional[EmailQueue] = None
_worker: Optional[EmailWorker] = None


def get_email_sender(config: MailSettings = Depends(lambda: settings)) -> EmailSender:
    """
    FastAPI dependency for EmailSender.
    
    Returns singleton instance.
    """
    global _sender
    if _sender is None:
        _sender = EmailSender(config)
    return _sender


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
    sender: EmailSender = Depends(get_email_sender),
    queue: EmailQueue = Depends(get_email_queue),
) -> EmailWorker:
    """
    FastAPI dependency for EmailWorker.
    
    Returns singleton instance.
    """
    global _worker
    if _worker is None:
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
    global _worker, _sender, _queue
    
    cfg = config or settings
    
    # Create instances if not exist
    if _sender is None:
        _sender = EmailSender(cfg)
    if _queue is None:
        _queue = EmailQueue(cfg)
    if _worker is None:
        _worker = EmailWorker(cfg, _sender, _queue)
    
    # Start worker
    await _worker.start()
    
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
        await _worker.stop()
