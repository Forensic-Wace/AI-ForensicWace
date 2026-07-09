"""Analysis job dispatch: message broker when configured, thread otherwise.

The API publishes only the process id; workers read everything else from the
``process_status`` table. Task names are the contract with services/worker.
"""

import logging
import threading

from ..config import get_settings

logger = logging.getLogger(__name__)

START_TASK = "analysis.start"
CONTROL_QUEUE = "control"


def dispatch_analysis(process_id: str) -> str:
    """Start an analysis job. Returns the executor used: 'queue' or 'thread'."""
    broker_url = get_settings().broker_url
    if broker_url:
        from celery import Celery

        Celery(broker=broker_url).send_task(START_TASK, args=[process_id], queue=CONTROL_QUEUE)
        return "queue"

    from .pipeline import run_analysis

    logger.warning("FW_BROKER_URL not set — running analysis %s in a background thread", process_id)
    threading.Thread(target=run_analysis, args=(process_id,), daemon=True).start()
    return "thread"
