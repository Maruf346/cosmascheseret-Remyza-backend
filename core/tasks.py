from celery import shared_task
from django.utils import timezone
from business.models import PhoneNumber, PhoneNumberStatus
from crm.models import FollowUpReminder
import logging

logger = logging.getLogger(__name__)

class PushNotificationService:
    @staticmethod
    def send_notification(user, title: str, body: str):
        """
        Mock service for triggering Push Notifications (e.g., via FCM or APNS).
        """
        logger.info(f"Sending Push Notification to {user}: {title} - {body}")
        pass

@shared_task
def check_trial_expirations():
    """Legacy no-op: free-trial phone-number subscriptions were removed for Sent.dm/IAP flow."""
    return
@shared_task
def send_follow_up_reminders():
    """
    Runs every minute. Finds reminders that are due and haven't been sent.
    """
    now = timezone.now()
    due_reminders = FollowUpReminder.objects.filter(
        scheduled_time__lte=now,
        is_sent=False
    )

    for reminder in due_reminders:
        title = "Follow-up Reminder"
        body = f"It's time to follow up with {reminder.lead.contact_number}. Note: {reminder.note}"
        
        # Assuming the organization owner receives the notification
        PushNotificationService.send_notification(reminder.organization.owner, title, body)
        
        reminder.is_sent = True
        reminder.save()

@shared_task
def poll_twilio_verification_status():
    pending_numbers = PhoneNumber.objects.filter(
        status=PhoneNumberStatus.PENDING,
        provider__isnull=False
    )

    if not pending_numbers.exists():
        return

    # In reality, you would instantiate your TwilioService here and query TrustHub
    for number in pending_numbers:
        try:
            # Example scaffold logic:
            # status = twilio_service.get_trusthub_status(number.provider.account_sid)
            # if status == 'approved':
            #     number.status = PhoneNumberStatus.ACTIVE
            # elif status == 'rejected':
            #     number.status = PhoneNumberStatus.REJECTED
            # number.save()
            pass
        except Exception as e:
            logger.exception(f"Failed to poll verification status for {number.phone_number}")
