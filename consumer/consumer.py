"""Main consumer entry point."""
import asyncio
import signal
import os
import logging
from consumer.worker import ScrapingWorker
from database.connection import DatabaseConnection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for the consumer service."""
    # Generate worker ID from environment or hostname
    worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")

    logger.info(f"Starting consumer with worker ID: {worker_id}")

    # Initialize database connections
    db = await DatabaseConnection.init_mongo()
    redis_client = await DatabaseConnection.init_redis()

    # Create worker
    worker = ScrapingWorker(db, redis_client, worker_id)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Start the worker
        await worker.start()
    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        # Cleanup
        await DatabaseConnection.close_connections()
        logger.info("Consumer shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
