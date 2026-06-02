from celery import Celery
import os
import time
import logging

logger = logging.getLogger(__name__)

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "rpg_api",
    broker = CELERY_BROKER_URL,
    backend = CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task
def example_background_task(message:str, duration:int=5):
    logger.info(f"Задача началась {message}")
    time.sleep(duration)
    logger.info(f"Задача завершилась {message}")
    return f"Обработано {message}"