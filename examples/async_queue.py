"""
Async queue example with background worker
"""

import asyncio

from mailing2fast_fastapi import EmailMessage, EmailQueue, EmailWorker


async def main():
    """Queue emails and process them with background worker."""
    # Create and start worker
    print("Starting email worker...")
    worker = EmailWorker()
    await worker.start()
    
    # Create queue
    queue = EmailQueue()
    await queue.connect()
    
    # Queue multiple emails
    print("\nQueueing emails...")
    
    emails = [
        EmailMessage(
            to=["user1@example.com"],
            subject="Welcome Email #1",
            html="<h1>Welcome to our service!</h1>",
        ),
        EmailMessage(
            to=["user2@example.com"],
            subject="Welcome Email #2",
            html="<h1>Welcome to our service!</h1>",
        ),
        EmailMessage(
            to=["user3@example.com"],
            subject="Welcome Email #3",
            html="<h1>Welcome to our service!</h1>",
        ),
    ]
    
    for email in emails:
        await queue.enqueue(email)
        print(f"  ✓ Queued: {email.subject}")
    
    # Check queue stats
    print("\nQueue statistics:")
    stats = await worker.get_stats()
    print(f"  Pending: {stats['queue_size']}")
    print(f"  Retry: {stats['retry_queue_size']}")
    print(f"  Failed (DLQ): {stats['dlq_size']}")
    
    # Let worker process emails
    print("\nProcessing emails (waiting 30 seconds)...")
    await asyncio.sleep(30)
    
    # Check stats again
    print("\nFinal statistics:")
    stats = await worker.get_stats()
    print(f"  Pending: {stats['queue_size']}")
    print(f"  Retry: {stats['retry_queue_size']}")
    print(f"  Failed (DLQ): {stats['dlq_size']}")
    
    # Cleanup
    print("\nStopping worker...")
    await worker.stop()
    await queue.disconnect()
    print("Done!")


async def queue_high_priority():
    """Queue a high-priority email."""
    queue = EmailQueue()
    await queue.connect()
    
    email = EmailMessage(
        to=["urgent@example.com"],
        subject="URGENT: High Priority Email",
        body="This email will be processed first.",
        priority="high",
    )
    
    # Add to front of queue (priority)
    await queue.enqueue(email, priority=True)
    print("High-priority email queued!")
    
    await queue.disconnect()


async def monitor_queue():
    """Monitor queue sizes."""
    queue = EmailQueue()
    await queue.connect()
    
    print("Queue Monitor")
    print("=" * 50)
    
    for _ in range(10):
        main_size = await queue.get_queue_size()
        retry_size = await queue.get_retry_queue_size()
        dlq_size = await queue.get_dlq_size()
        
        print(f"Main: {main_size:3d} | Retry: {retry_size:3d} | DLQ: {dlq_size:3d}")
        await asyncio.sleep(2)
    
    await queue.disconnect()


if __name__ == "__main__":
    # Run main example
    asyncio.run(main())
    
    # Uncomment to run other examples:
    # asyncio.run(queue_high_priority())
    # asyncio.run(monitor_queue())
