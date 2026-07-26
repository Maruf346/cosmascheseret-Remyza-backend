from django.utils import timezone
from subscription.models import UserSubscription
from subscription.choices import SubscriptionStatus
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from subscription.models import (
    UserSubscription,
    Payment,
)
from subscription.choices import (
    BillingCycle,
    SubscriptionStatus,
    PaymentStatus,
)

class SubscriptionValidationService:
    @staticmethod
    def get_active_subscription(organization):
        now = timezone.now()
        return UserSubscription.objects.select_related("plan").filter(
            organization=organization, status=SubscriptionStatus.ACTIVE, start_date__lte=now, end_date__gte=now
        ).first()

    @classmethod
    def has_active_subscription(cls, organization):
        return cls.get_active_subscription(organization) is not None

class SubscriptionPurchaseService:
    @classmethod
    @transaction.atomic
    def claim_free_trail(cls, user, organization, trail_plan, billing_cycle, day):
        if SubscriptionValidationService.has_active_subscription(organization):
            raise ValidationError({"detail": "You already have an active subscription."})
        now = timezone.now()
        end_date = now + timedelta(days=day)
        subscription = UserSubscription.objects.create(
            user=user,
            organization=organization,
            plan=trail_plan,
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            end_date=end_date,
            next_billing_date=end_date,
            auto_renew=False
        )
        return {"subscription": subscription, "message": "Free Trail Claim Successfully."}

    @classmethod
    @transaction.atomic
    def purchase(cls, organization, plan, billing_cycle):
        if SubscriptionValidationService.has_active_subscription(organization):
            raise ValidationError({"detail": "You already have an active subscription."})

        now = timezone.now()
        if billing_cycle == BillingCycle.MONTHLY:
            end_date = now + timedelta(days=30)

        elif billing_cycle == BillingCycle.YEARLY:
            end_date = now + timedelta(days=365)
        else:
            raise ValidationError({"billing_cycle": "Invalid billing cycle."})

        subscription = UserSubscription.objects.create(
            organization=organization,
            plan=plan,
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.AWAITING_PAYMENT,
            start_date=now,
            end_date=end_date,
            next_billing_date=end_date,
        )
        payment = Payment.objects.create(
            subscription=subscription,
            amount=plan.price,
            currency=plan.currency,
            status=PaymentStatus.PENDING,
        )
        return {"subscription": subscription, "payment": payment}


    

