"""Celery application for the analysis workers.

Queues (one per stage, so GPU/IO-bound work scales independently):
- ``control``: job orchestration (extraction + fan-out)
- ``media``:   audio transcription, image OCR/captioning
- ``text``:    PII/password analyzers + persistence
- ``fw.dead``: dead-letter queue — tasks that exhausted their retries land
  here as JSON for inspection (RabbitMQ management UI or any consumer).

Queue depth on ``media``/``text`` is the autoscaling signal (KEDA, Phase 5).
"""

from celery import Celery
from kombu import Queue

from forensicwace_core.config import get_settings

CONTROL_QUEUE = "control"
MEDIA_QUEUE = "media"
TEXT_QUEUE = "text"
DEAD_QUEUE = Queue("fw.dead", durable=True)

app = Celery("forensicwace", broker=get_settings().broker_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    # A message is acknowledged only after the task completed, and requeued if
    # the worker dies mid-task: no analysis is lost on worker restarts.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue=TEXT_QUEUE,
    task_queues=[Queue(CONTROL_QUEUE), Queue(MEDIA_QUEUE), Queue(TEXT_QUEUE), DEAD_QUEUE],
)

app.autodiscover_tasks(["forensicwace_worker"])

from . import tasks  # noqa: E402,F401 — register task definitions
