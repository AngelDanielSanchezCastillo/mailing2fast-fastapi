"""
Background worker for processing email queue
"""

import asyncio
import logging
import signal
from typing import Optional

from .models import EmailStatus, QueuedEmail
from .queue import EmailQueue
from .sender import EmailSender
from .settings import MailSettings, settings

logger = logging.getLogger(__name__)


class EmailWorker:
    """Background worker for processing email queue."""

    def __init__(
        self,
        config: Optional[MailSettings] = None,
        sender: Optional[EmailSender] = None,
        queue: Optional[EmailQueue] = None,
    ):
        """
        Initialize email worker.
        
        Args:
            config: Mail settings (uses global settings if not provided)
            sender: Email sender instance (creates new if not provided)
            queue: Email queue instance (creates new if not provided)
        """
        self.config = config or settings
        self.sender = sender or EmailSender(self.config)
        self.queue = queue or EmailQueue(self.config)
        
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the worker."""
        if self._running:
            logger.warning("Worker is already running")
            return
        
        self._running = True
        
        # Connect to Redis
        await self.queue.connect()
        
        logger.info("Email worker started")
        
        # Start processing loop
        self._task = asyncio.create_task(self._process_loop())
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        if not self._running:
            return
        
        logger.info("Stopping email worker...")
        self._running = False
        
        # Cancel processing task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Disconnect from Redis
        await self.queue.disconnect()
        
        logger.info("Email worker stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        poll_interval = self.config.queue.worker_poll_interval
        
        while self._running:
            try:
                # Process retry queue first (emails that need retry)
                await self._process_retry_queue()
                
                # Process main queue
                await self._process_main_queue()
                
                # Small delay to prevent tight loop
                await asyncio.sleep(poll_interval)
                
            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                # Continue processing despite errors
                await asyncio.sleep(poll_interval)

    async def _process_main_queue(self) -> None:
        """Process emails from main queue."""
        batch_size = self.config.queue.batch_size
        
        for _ in range(batch_size):
            # Non-blocking dequeue
            queued_email = await self.queue.dequeue(timeout=0)
            
            if not queued_email:
                # Queue is empty
                break
            
            await self._send_email(queued_email)

    async def _process_retry_queue(self) -> None:
        """Process emails from retry queue that are ready."""
        # Get emails ready for retry
        retry_emails = await self.queue.get_retry_emails()
        
        for queued_email in retry_emails:
            logger.info(
                f"Retrying email (attempt {queued_email.retry_count + 1}): "
                f"{queued_email.email.subject}"
            )
            await self._send_email(queued_email)

    async def _send_email(self, queued_email: QueuedEmail) -> None:
        """
        Send a queued email.
        
        Args:
            queued_email: Email to send
        """
        try:
            # Send email
            result = await self.sender.send_email(queued_email.email)
            
            if result.is_success():
                logger.info(
                    f"Successfully sent email: {queued_email.email.subject} "
                    f"(message_id: {result.message_id})"
                )
            else:
                # Failed - requeue for retry
                logger.warning(
                    f"Failed to send email: {queued_email.email.subject} "
                    f"(error: {result.error})"
                )
                await self.queue.requeue_for_retry(queued_email, result.error or "Unknown error")
                
        except Exception as e:
            # Unexpected error - requeue for retry
            logger.error(
                f"Unexpected error sending email: {queued_email.email.subject}",
                exc_info=True,
            )
            await self.queue.requeue_for_retry(queued_email, str(e))

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_event_loop()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.stop())
                )
        except NotImplementedError:
            # Signal handlers not supported on this platform (e.g., Windows)
            pass

    async def get_stats(self) -> dict:
        """
        Get worker statistics.
        
        Returns:
            Dictionary with queue sizes and worker status
        """
        return {
            "running": self._running,
            "queue_size": await self.queue.get_queue_size(),
            "retry_queue_size": await self.queue.get_retry_queue_size(),
            "dlq_size": await self.queue.get_dlq_size(),
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


async def run_worker(config: Optional[MailSettings] = None) -> None:
    """
    Run the email worker.
    
    This is a convenience function for running the worker standalone.
    
    Args:
        config: Mail settings (uses global settings if not provided)
    """
    worker = EmailWorker(config)
    
    try:
        await worker.start()
        
        # Keep running until interrupted
        while worker._running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Run worker
    asyncio.run(run_worker())
