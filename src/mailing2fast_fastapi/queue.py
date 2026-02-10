"""
Redis queue manager for email processing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis

from .models import EmailMessage, QueuedEmail
from .settings import MailSettings, settings

logger = logging.getLogger(__name__)


class EmailQueue:
    """Redis-based FIFO queue for email messages."""

    def __init__(self, config: Optional[MailSettings] = None):
        """
        Initialize email queue.
        
        Args:
            config: Mail settings (uses global settings if not provided)
        """
        self.config = config or settings
        self._pool: Optional[redis.ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is not None:
            return
        
        redis_config = self.config.redis
        
        # Create connection pool
        self._pool = redis.ConnectionPool(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.password,
            max_connections=redis_config.max_connections,
            decode_responses=False,  # We'll handle JSON encoding/decoding
        )
        
        # Create Redis client
        self._redis = redis.Redis(connection_pool=self._pool)
        
        # Test connection
        await self._redis.ping()
        logger.info(f"Connected to Redis at {redis_config.host}:{redis_config.port}")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
        
        logger.info("Disconnected from Redis")

    async def enqueue(self, email: EmailMessage, priority: bool = False) -> None:
        """
        Add email to queue.
        
        Args:
            email: Email message to queue
            priority: If True, add to front of queue (LIFO for high priority)
        """
        await self._ensure_connected()
        
        # Create queued email with metadata
        queued_email = QueuedEmail(
            email=email,
            queued_at=datetime.utcnow(),
            retry_count=0,
        )
        
        # Serialize to JSON
        data = queued_email.model_dump_json()
        
        # Add to queue (LPUSH for FIFO, RPUSH for priority)
        queue_name = self.config.redis.queue_name
        
        if priority:
            # High priority: add to front (will be processed first)
            await self._redis.rpush(queue_name, data)
            logger.info(f"Added high-priority email to queue: {email.subject}")
        else:
            # Normal: add to back (FIFO)
            await self._redis.lpush(queue_name, data)
            logger.info(f"Added email to queue: {email.subject}")

    async def dequeue(self, timeout: int = 0) -> Optional[QueuedEmail]:
        """
        Get next email from queue.
        
        Args:
            timeout: Timeout in seconds (0 = non-blocking, None = block forever)
            
        Returns:
            QueuedEmail or None if queue is empty (when timeout=0)
        """
        await self._ensure_connected()
        
        queue_name = self.config.redis.queue_name
        
        # BRPOP for blocking pop from right (FIFO)
        if timeout == 0:
            # Non-blocking
            data = await self._redis.rpop(queue_name)
            if not data:
                return None
        else:
            # Blocking with timeout
            result = await self._redis.brpop(queue_name, timeout=timeout)
            if not result:
                return None
            _, data = result
        
        # Deserialize
        queued_email = QueuedEmail.model_validate_json(data)
        logger.info(f"Dequeued email: {queued_email.email.subject}")
        
        return queued_email

    async def requeue_for_retry(
        self,
        queued_email: QueuedEmail,
        error: str,
    ) -> None:
        """
        Move email to retry queue.
        
        Args:
            queued_email: Email that failed to send
            error: Error message
        """
        await self._ensure_connected()
        
        # Update metadata
        queued_email.retry_count += 1
        queued_email.last_error = error
        
        # Calculate next retry time with exponential backoff
        delay = self.config.queue.retry_delay * (2 ** (queued_email.retry_count - 1))
        queued_email.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        
        # Check if max retries exceeded
        if queued_email.retry_count >= self.config.queue.max_retries:
            logger.warning(
                f"Email exceeded max retries ({self.config.queue.max_retries}), "
                f"moving to DLQ: {queued_email.email.subject}"
            )
            await self.move_to_dlq(queued_email)
            return
        
        # Add to retry queue with score (timestamp for when to retry)
        retry_queue = self.config.redis.retry_queue_name
        score = queued_email.next_retry_at.timestamp()
        data = queued_email.model_dump_json()
        
        await self._redis.zadd(retry_queue, {data: score})
        logger.info(
            f"Requeued email for retry #{queued_email.retry_count} "
            f"at {queued_email.next_retry_at}: {queued_email.email.subject}"
        )

    async def get_retry_emails(self) -> list[QueuedEmail]:
        """
        Get emails from retry queue that are ready to retry.
        
        Returns:
            List of emails ready for retry
        """
        await self._ensure_connected()
        
        retry_queue = self.config.redis.retry_queue_name
        now = datetime.utcnow().timestamp()
        
        # Get all emails with score <= now (ready to retry)
        results = await self._redis.zrangebyscore(retry_queue, 0, now)
        
        if not results:
            return []
        
        # Remove from retry queue
        await self._redis.zremrangebyscore(retry_queue, 0, now)
        
        # Deserialize
        emails = [QueuedEmail.model_validate_json(data) for data in results]
        logger.info(f"Retrieved {len(emails)} emails ready for retry")
        
        return emails

    async def move_to_dlq(self, queued_email: QueuedEmail) -> None:
        """
        Move email to dead letter queue (permanent failure).
        
        Args:
            queued_email: Email that permanently failed
        """
        await self._ensure_connected()
        
        dlq_name = self.config.redis.dead_letter_queue_name
        data = queued_email.model_dump_json()
        
        await self._redis.lpush(dlq_name, data)
        logger.error(
            f"Moved email to DLQ after {queued_email.retry_count} retries: "
            f"{queued_email.email.subject}"
        )

    async def get_queue_size(self) -> int:
        """Get number of emails in main queue."""
        await self._ensure_connected()
        return await self._redis.llen(self.config.redis.queue_name)

    async def get_retry_queue_size(self) -> int:
        """Get number of emails in retry queue."""
        await self._ensure_connected()
        return await self._redis.zcard(self.config.redis.retry_queue_name)

    async def get_dlq_size(self) -> int:
        """Get number of emails in dead letter queue."""
        await self._ensure_connected()
        return await self._redis.llen(self.config.redis.dead_letter_queue_name)

    async def clear_queue(self) -> None:
        """Clear main queue (use with caution!)."""
        await self._ensure_connected()
        await self._redis.delete(self.config.redis.queue_name)
        logger.warning("Cleared main email queue")

    async def clear_retry_queue(self) -> None:
        """Clear retry queue (use with caution!)."""
        await self._ensure_connected()
        await self._redis.delete(self.config.redis.retry_queue_name)
        logger.warning("Cleared retry queue")

    async def clear_dlq(self) -> None:
        """Clear dead letter queue (use with caution!)."""
        await self._ensure_connected()
        await self._redis.delete(self.config.redis.dead_letter_queue_name)
        logger.warning("Cleared dead letter queue")

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is established."""
        if self._redis is None:
            await self.connect()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
