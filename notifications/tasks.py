from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)


@shared_task(name="notifications.cleanup_read_notifications")
def cleanup_read_notifications(days=90):
    """Delete read notifications older than the retention window."""
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = Notification.objects.filter(is_read=True, read_at__lt=cutoff).delete()
    logger.info("Deleted %s old read notification(s).", deleted_count)
    return deleted_count