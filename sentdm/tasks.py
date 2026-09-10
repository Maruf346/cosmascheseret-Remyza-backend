from celery import shared_task

from .choices import SentDMWebhookEventStatus
from .models import SentDMWebhookEvent
from .services import process_sentdm_webhook_event


@shared_task(bind=True, autoretry_for=(), max_retries=0, queue="sentdm")
def process_sentdm_webhook_event_task(self, event_id):
    event = SentDMWebhookEvent.objects.filter(pk=event_id).first()
    if not event:
        return {"processed": False, "action": "missing_event", "event_id": event_id}

    if event.status == SentDMWebhookEventStatus.PROCESSED:
        return {"processed": True, "action": "already_processed", "event_id": event_id}

    return process_sentdm_webhook_event(event)
