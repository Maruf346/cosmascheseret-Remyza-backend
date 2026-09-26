import logging

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.choices import UserType
from .models import Notification, NotificationPriority, NotificationType

try:
    from channels.layers import get_channel_layer
except ImportError:  # pragma: no cover - production dependency guard
    get_channel_layer = None

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Creates REST notifications and pushes websocket notifications to admins only."""

    @staticmethod
    def is_admin_recipient(user):
        return bool(
            user
            and (user.is_staff or user.is_superuser or getattr(user, "user_type", None) == UserType.ADMIN)
        )

    @staticmethod
    def create_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
        push_websocket: bool | None = None,
    ):
        if not user:
            return None

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )

        should_push_ws = NotificationService.is_admin_recipient(user) if push_websocket is None else push_websocket
        if should_push_ws and NotificationService.is_admin_recipient(user):
            transaction.on_commit(lambda: NotificationService._send_websocket(notification))

        return notification

    @staticmethod
    def _send_websocket(notification):
        if get_channel_layer is None:
            logger.warning("Channels is not installed; websocket notification skipped.")
            return False
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                logger.warning("No channel layer configured; websocket notification skipped.")
                return False
            async_to_sync(channel_layer.group_send)(
                f"admin_notifications_{notification.user_id}",
                {
                    "type": "notification.message",
                    "notification_id": str(notification.id),
                    "notification_type": notification.notification_type,
                    "title": notification.title,
                    "body": notification.body,
                    "data": notification.data,
                    "priority": notification.priority,
                    "created_at": notification.created_at.isoformat(),
                    "unread_count": Notification.objects.filter(user=notification.user, is_read=False).count(),
                },
            )
            return True
        except Exception as exc:  # pragma: no cover - depends on channel backend
            logger.exception("Websocket notification failed for user %s: %s", notification.user_id, exc)
            return False

    @staticmethod
    def notify_admins(notification_type, title, body, data=None, priority=NotificationPriority.NORMAL):
        notifications = []
        admins = User.objects.filter(models_q_admin_users()).distinct()
        for admin in admins:
            notifications.append(
                NotificationService.create_notification(
                    user=admin,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    data=data or {},
                    priority=priority,
                    push_websocket=True,
                )
            )
        return notifications


def models_q_admin_users():
    from django.db.models import Q

    return Q(is_staff=True) | Q(is_superuser=True) | Q(user_type=UserType.ADMIN)


class NotificationTemplates:
    """Chesera notification templates used by API views, services, and Celery tasks."""

    @staticmethod
    def welcome_user(user):
        return NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.WELCOME,
            title="Welcome to Chesera",
            body="Your Chesera dashboard is ready. Messaging activates after your paid subscription and business compliance setup are completed.",
            data={"user_id": str(user.id)},
            priority=NotificationPriority.NORMAL,
            push_websocket=False,
        )

    @staticmethod
    def new_user_registered(user):
        label = getattr(user, "full_name", "") or getattr(user, "email", "") or getattr(user, "phone_number", "")
        return NotificationService.notify_admins(
            notification_type=NotificationType.NEW_USER,
            title="New user signup",
            body=f"{label} started signup on Chesera.",
            data={"user_id": str(user.id), "phone_number": getattr(user, "phone_number", "")},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def subscription_recorded(subscription):
        user = subscription.user
        active = bool(subscription.is_subscription_active)
        NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_ACTIVE if active else NotificationType.SUBSCRIPTION_CREATED,
            title="Subscription active" if active else "Subscription received",
            body=(
                "Your paid subscription is active. You can continue the Sent.dm messaging activation steps."
                if active
                else "Your subscription record was received. Messaging unlocks when the store confirms it is active."
            ),
            data={"subscription_id": str(subscription.id), "product_id": subscription.product_id, "active": active},
            priority=NotificationPriority.NORMAL,
            push_websocket=False,
        )
        return NotificationService.notify_admins(
            notification_type=NotificationType.SUBSCRIPTION_ACTIVE if active else NotificationType.SUBSCRIPTION_CREATED,
            title="Subscription record created",
            body=f"A subscription record was created for {getattr(user, 'email', '') or getattr(user, 'phone_number', '')}.",
            data={"subscription_id": str(subscription.id), "user_id": str(user.id), "active": active},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def sentdm_profile_requested(profile):
        user = profile.user or getattr(profile.organization, "owner", None)
        if user:
            NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.SENTDM_PROFILE_REQUESTED,
                title="Messaging activation started",
                body="Your Sent.dm Sender Profile request was accepted. Messaging activation usually takes 1-3 business days.",
                data={"profile_id": profile.profile_id, "status": profile.status},
                priority=NotificationPriority.NORMAL,
                push_websocket=False,
            )
        return NotificationService.notify_admins(
            notification_type=NotificationType.SENTDM_PROFILE_REQUESTED,
            title="Sender Profile requested",
            body=f"A Sent.dm Sender Profile was requested for {profile.organization.name}.",
            data={"profile_id": profile.profile_id, "organization_id": str(profile.organization_id), "status": profile.status},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def sentdm_profile_completed(profile):
        user = profile.user or getattr(profile.organization, "owner", None)
        if user:
            NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.SENTDM_PROFILE_COMPLETED,
                title="Sender Profile onboarding submitted",
                body="Your Sender Profile onboarding completion request was submitted to Sent.dm.",
                data={"profile_id": profile.profile_id, "status": profile.status},
                priority=NotificationPriority.NORMAL,
                push_websocket=False,
            )
        return NotificationService.notify_admins(
            notification_type=NotificationType.SENTDM_PROFILE_COMPLETED,
            title="Sender Profile onboarding submitted",
            body=f"Sent.dm onboarding completion was submitted for {profile.organization.name}.",
            data={"profile_id": profile.profile_id, "organization_id": str(profile.organization_id), "status": profile.status},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def sentdm_campaign_requested(campaign):
        profile = campaign.profile
        user = profile.user or getattr(profile.organization, "owner", None)
        if user:
            NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.SENTDM_CAMPAIGN_REQUESTED,
                title="10DLC campaign submitted",
                body="Your 10DLC campaign request was submitted. Activation usually takes 1-3 business days.",
                data={"campaign_id": campaign.campaign_id, "profile_id": profile.profile_id, "status": campaign.status},
                priority=NotificationPriority.NORMAL,
                push_websocket=False,
            )
        return NotificationService.notify_admins(
            notification_type=NotificationType.SENTDM_CAMPAIGN_REQUESTED,
            title="10DLC campaign submitted",
            body=f"A 10DLC campaign was submitted for {profile.organization.name}.",
            data={"campaign_id": campaign.campaign_id, "profile_id": profile.profile_id, "status": campaign.status},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def whatsapp_connection_requested(profile):
        user = profile.user or getattr(profile.organization, "owner", None)
        if user:
            NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.WHATSAPP_CONNECTION_REQUESTED,
                title="WhatsApp connection submitted",
                body="Your WhatsApp Business connection was submitted. WhatsApp becomes available after Sent.dm accepts the configuration.",
                data={"profile_id": profile.profile_id, "whatsapp_status": profile.whatsapp_connection_status},
                priority=NotificationPriority.NORMAL,
                push_websocket=False,
            )
        return NotificationService.notify_admins(
            notification_type=NotificationType.WHATSAPP_CONNECTION_REQUESTED,
            title="WhatsApp connection submitted",
            body=f"An agent-owned WhatsApp connection was submitted for {profile.organization.name}.",
            data={"profile_id": profile.profile_id, "whatsapp_status": profile.whatsapp_connection_status},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def new_lead_captured(lead, channel="auto"):
        user = getattr(lead.organization, "owner", None)
        if user:
            NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.NEW_LEAD,
                title="New lead captured",
                body=f"A new lead messaged your Chesera number from {lead.contact_number}.",
                data={"lead_id": str(lead.id), "contact_number": lead.contact_number, "channel": channel},
                priority=NotificationPriority.HIGH,
                push_websocket=False,
            )
        return NotificationService.notify_admins(
            notification_type=NotificationType.NEW_LEAD,
            title="New lead captured",
            body=f"A new lead was captured for {lead.organization.name}.",
            data={"lead_id": str(lead.id), "organization_id": str(lead.organization_id), "channel": channel},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def system_alert(user, title, body, data=None):
        return NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            body=body,
            data=data or {},
            priority=NotificationPriority.HIGH,
        )

def safe_notify(callable_obj, *args, **kwargs):
    """Run a notification hook without breaking the business flow that triggered it."""
    try:
        return callable_obj(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive integration guard
        logger.exception("Notification hook failed: %s", exc)
        return None
