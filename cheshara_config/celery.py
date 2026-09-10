import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cheshara_config.settings")

app = Celery("cheshara_config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
