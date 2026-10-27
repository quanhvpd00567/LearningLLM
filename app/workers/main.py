"""Run `python -m app.workers.main` or add --once / --drain."""
import argparse
import asyncio
import logging
import signal
import socket
from uuid import uuid4

import httpx

from app.core.observability import configure_logging
from app.core.config import get_settings
from app.db.session import create_database
from app.services.embedding import EmbeddingService
from app.workers.embedding import EmbeddingWorker

logger = logging.getLogger(__name__)


async def main(once=False, drain=False):
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    engine, sessions = create_database(settings.database_url)
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=settings.embedding_timeout_seconds) as client:
            worker = EmbeddingWorker(
                sessions, EmbeddingService(client, settings.embedding_model, settings.embedding_dimensions),
                worker_id=f"{socket.gethostname()}-{uuid4()}", batch_size=settings.embedding_batch_size,
                lease_seconds=settings.embedding_job_lease_seconds, retry_seconds=settings.embedding_job_retry_seconds,
            )
            logger.info("Worker started model=%s", settings.embedding_model)
            while not stop.is_set():
                try:
                    processed = await worker.run_once()
                except Exception as exc:
                    logger.error("Worker database/queue error type=%s", type(exc).__name__)
                    if once or drain:
                        raise
                    processed = False
                if once or (drain and not processed):
                    break
                if not processed:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=settings.embedding_job_poll_seconds)
                    except TimeoutError:
                        pass
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll PostgreSQL embedding jobs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Attempt one ready job and exit")
    mode.add_argument("--drain", action="store_true", help="Run until no jobs are ready; delayed retries remain queued")
    args = parser.parse_args()
    configure_logging()
    asyncio.run(main(args.once, args.drain))
