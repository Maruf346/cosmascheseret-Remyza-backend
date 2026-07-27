from django.db import models
from django.utils import timezone
from datetime import timedelta


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            status="ACTIVE",
            is_deleted=False
        )

    def verified(self):
        return self.filter(
            is_phone_verified=True
        )

    def recently_active(self):
        return self.filter(
            last_activity_at__gte=timezone.now() - timedelta(days=7)
        )

class OTPVerificationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False, is_used=False, expires_at__gt=timezone.now())

    def expired(self):
        return self.filter(expires_at__lte=timezone.now())

    def used(self):
        return self.filter(is_used=True)

    def pending(self):
        return self.active()

    def for_phone(self, phone_number):
        return self.filter(phone_number=phone_number)

    def for_user(self, user):
        return self.filter(user=user)

    def for_purpose(self, purpose):
        return self.filter(purpose=purpose)

    def latest(self):
        return self.order_by("-created_at")


