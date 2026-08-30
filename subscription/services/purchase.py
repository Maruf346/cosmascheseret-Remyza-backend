from django.db.models import Q
from django.utils import timezone

from subscription.models import UserSubscription


class SubscriptionValidationService:
    @classmethod
    def get_paid_active_subscription(cls, user):
        return cls.get_current_subscription(user)

    @classmethod
    def get_current_subscription(cls, user):
        now = timezone.now()
        return (
            UserSubscription.objects
            .select_related("user", "organization")
            .filter(user=user, is_subscription_active=True)
            .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=now))
            .order_by("-expiry_date", "-created_at")
            .first()
        )

    @staticmethod
    def get_active_subscription(user):
        return SubscriptionValidationService.get_current_subscription(user)

    @classmethod
    def has_active_subscription(cls, user):
        return cls.get_current_subscription(user) is not None

    @classmethod
    def get_active_free_trail_subscription(cls, user):
        return None

    @classmethod
    def has_active_subscription_with_free_trial(cls, user):
        return False

    @classmethod
    def get_free_trail_subscription(cls, user):
        return None

    @classmethod
    def has_free_trail_claimed(cls, user):
        return False