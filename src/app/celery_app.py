# app/celery_app.py
from celery import Celery
from celery.schedules import crontab
from .core.config import settings

app = Celery(
    __name__,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True

app.conf.timezone = "UTC"
app.conf.beat_schedule = {
    "remove-expired-tokens-every-3-minutes": {
        "task": "app.tasks.remove_expired_tokens",
        "schedule": crontab(minute="*/3"),
        "options": {"queue": "maintenance"},
    },
}
app.autodiscover_tasks(["app.tasks"])
