from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "tradingbot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "scan-all-users-every-30s": {
            "task": "app.workers.bot_worker.scan_all_users",
            "schedule": 30.0,
        },
    },
)

import app.workers.bot_worker  # noqa
