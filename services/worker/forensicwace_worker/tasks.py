"""Analysis tasks. Granularity: one task per (message, stage).

Retry policy: exponential backoff, 3 attempts. A task that exhausts its
retries is published to the ``fw.dead`` queue and counted in
``process_status.failed_messages`` so the failure is visible in the UI.
"""

import logging

from celery import Task, chain

from forensicwace_core.analysis import pipeline
from forensicwace_core.analysis.types import Message
from forensicwace_core.resultsdb import repositories
from forensicwace_core.resultsdb.engine import init_db, session_scope

from .celery_app import CONTROL_QUEUE, DEAD_QUEUE, MEDIA_QUEUE, TEXT_QUEUE, app

logger = logging.getLogger(__name__)

RETRY_POLICY = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 120,
    "retry_kwargs": {"max_retries": 3},
}


class MessageTask(Task):
    """Per-message task: a final failure is recorded and dead-lettered."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        process_id = kwargs.get("process_id") or (args[1] if len(args) > 1 else None)
        logger.error("Task %s failed permanently for process %s: %s", self.name, process_id, exc)
        if process_id:
            pipeline.record_message_done(process_id, failed=True)
        try:
            with self.app.producer_pool.acquire(block=True) as producer:
                producer.publish(
                    {"task": self.name, "args": args, "kwargs": kwargs, "error": str(exc)},
                    exchange="",
                    routing_key=DEAD_QUEUE.name,
                    serializer="json",
                    declare=[DEAD_QUEUE],
                )
        except Exception:
            logger.exception("Could not publish failed task to the dead-letter queue")


@app.task(name="analysis.start", queue=CONTROL_QUEUE, bind=True, **RETRY_POLICY)
def start_analysis(self, process_id: str) -> None:
    """Extract the selected messages and fan out one chain per message."""
    init_db()
    with session_scope() as session:
        process = repositories.get_process(session, process_id)
        if process is None:
            logger.error("Unknown analysis process %s", process_id)
            return
        requested = [a for a in (process.analyzers or "").split(",") if a]
        try:
            messages = pipeline.extract_messages(process)
        except Exception as exc:
            if self.request.retries >= self.retry_kwargs["max_retries"]:
                pipeline.mark_process_error(process_id, f"Extraction failed: {exc}")
            raise

    if not messages:
        pipeline.finish_empty(process_id)
        return

    pipeline.start_processing(process_id, len(messages))
    for message in messages:
        payload = message.to_dict()
        if pipeline.needs_media_stage(message, requested):
            chain(
                enrich_media.s(payload, process_id=process_id, requested=requested),
                analyze_text.s(process_id=process_id, requested=requested),
            ).apply_async()
        else:
            analyze_text.apply_async(args=[payload], kwargs={"process_id": process_id, "requested": requested})


@app.task(name="analysis.enrich_media", queue=MEDIA_QUEUE, base=MessageTask, **RETRY_POLICY)
def enrich_media(payload: dict, process_id: str, requested: list[str]) -> dict:
    """Audio transcription / image OCR+caption; returns the enriched payload."""
    message = Message.from_dict(payload)
    pipeline.enrich_media(message, requested)
    return message.to_dict()


@app.task(name="analysis.analyze_text", queue=TEXT_QUEUE, base=MessageTask, **RETRY_POLICY)
def analyze_text(payload: dict, process_id: str, requested: list[str]) -> None:
    """PII/password analysis + persistence + progress accounting."""
    init_db()
    message = Message.from_dict(payload)
    pipeline.analyze_and_persist(message, process_id, requested)
    pipeline.record_message_done(process_id)
