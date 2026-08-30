from rest_framework.permissions import BasePermission

from subscription.services.purchase import SubscriptionValidationService


class HasActivePaidSubscription(BasePermission):
    message = (
        "Messaging setup is available only after a paid subscription is active. "
        "Free users can use the dashboard, but SMS/RCS/WhatsApp activation is disabled until they upgrade."
    )

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return SubscriptionValidationService.get_paid_active_subscription(user) is not None