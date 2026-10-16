"""PostgreSQL queue. Every claim gets a fresh token to fence expired workers."""
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update

from app.chatbot.rag.chunking import PIPELINE_VERSION
from app.db.models import AdminSettings, Job


@dataclass(frozen=True)
class Claim:
    id: UUID
    token: str
    source_type: str
    source_id: UUID
    source_version: int
    job_type: str
    embedding_model: str
    pipeline_version: int


class JobQueue:
    def __init__(self, sessions, model: str, worker_id: str, lease_seconds: float = 600, retry_seconds: float = 5):
        self.sessions = sessions
        self.model = model
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.retry_seconds = retry_seconds

    async def recover_stale(self) -> int:
        async with self.sessions.begin() as session:
            now = await session.scalar(select(func.clock_timestamp()))
            jobs = (await session.scalars(select(Job).where(
                Job.status == "processing", Job.embedding_model == self.model,
                Job.pipeline_version == PIPELINE_VERSION,
                or_(Job.locked_at.is_(None), Job.locked_at < now - timedelta(seconds=self.lease_seconds)),
            ).order_by(Job.created_at, Job.id).with_for_update(skip_locked=True).limit(50))).all()
            for job in jobs:
                job.status = "failed" if job.attempts >= job.max_attempts else "pending"
                job.available_at = now
                job.completed_at = now if job.status == "failed" else None
                job.last_error = "Worker lease expired"
                job.locked_at = None
                job.locked_by = None
            return len(jobs)

    async def claim(self) -> Claim | None:
        async with self.sessions.begin() as session:
            if await session.scalar(select(AdminSettings.embedding_paused).where(AdminSettings.id == 1)):
                return None
            job = await session.scalar(select(Job).where(
                Job.status == "pending", Job.available_at <= func.clock_timestamp(),
                Job.embedding_model == self.model, Job.pipeline_version == PIPELINE_VERSION,
                Job.attempts < Job.max_attempts,
            ).order_by(Job.available_at, Job.created_at, Job.id).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return None
            job.status = "processing"
            job.attempts += 1
            job.locked_by = f"{self.worker_id}:{uuid4()}"
            job.locked_at = await session.scalar(select(func.clock_timestamp()))
            job.completed_at = None
            return Claim(job.id, job.locked_by, job.source_type, job.source_id,
                         job.source_version, job.job_type, job.embedding_model, job.pipeline_version)

    async def heartbeat(self, claim: Claim) -> bool:
        async with self.sessions.begin() as session:
            result = await session.execute(update(Job).where(
                Job.id == claim.id, Job.status == "processing", Job.locked_by == claim.token,
            ).values(locked_at=func.clock_timestamp()))
            return result.rowcount == 1

    async def fail(self, claim: Claim, error: str):
        async with self.sessions.begin() as session:
            job = await session.scalar(select(Job).where(
                Job.id == claim.id, Job.status == "processing", Job.locked_by == claim.token,
            ).with_for_update())
            if job is None:
                return
            now = await session.scalar(select(func.clock_timestamp()))
            terminal = job.attempts >= job.max_attempts
            job.status = "failed" if terminal else "pending"
            job.available_at = now + timedelta(seconds=min(300, self.retry_seconds * 2 ** min(job.attempts - 1, 10)))
            job.completed_at = now if terminal else None
            job.last_error = error[:1000]
            job.locked_at = None
            job.locked_by = None
