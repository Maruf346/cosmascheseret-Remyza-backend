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
from ..choices import PlanType

class SubscriptionValidationService:
    @classmethod
    def get_paid_active_subscription(cls, user):
        now = timezone.now()
        return UserSubscription.objects.select_related("plan").filter(
            user=user, plan__plan_type=PlanType.PAID, status=SubscriptionStatus.ACTIVE, start_date__lte=now, expires_at__gte=now
        ).first()

    @classmethod
    def get_current_subscription(cls, user):
        now = timezone.now()
        return UserSubscription.objects.select_related("plan").filter(
            user=user, status=SubscriptionStatus.ACTIVE, start_date__lte=now, expires_at__gte=now
        ).first()

    @staticmethod
    def get_active_subscription(user):
        now = timezone.now()
        return UserSubscription.objects.select_related("plan").filter(
            user=user, plan__plan_type=PlanType.PAID, status=SubscriptionStatus.ACTIVE, start_date__lte=now, expires_at__gte=now
        ).first()

    @classmethod
    def has_active_subscription(cls, user):
        get_active_subscription = cls.get_active_subscription(user)
        if get_active_subscription:
            return get_active_subscription.plan.plan_type == PlanType.PAID
        return False

    @classmethod
    def get_active_free_trail_subscription(cls, user):
        now = timezone.now()
        return UserSubscription.objects.select_related("plan").filter(
            user=user, plan__plan_type=PlanType.FREE_TRAIL, status=SubscriptionStatus.ACTIVE, start_date__lte=now, expires_at__gte=now
        ).first()

    @classmethod
    def has_active_subscription_with_free_trial(cls, user):
        get_active_subscription = cls.get_active_free_trail_subscription(user)
        return get_active_subscription is not None
    

    @classmethod
    def get_free_trail_subscription(cls, user):
        return UserSubscription.objects.select_related("plan").filter(
            user=user, plan__plan_type=PlanType.FREE_TRAIL
        ).first()

    @classmethod
    def has_free_trail_claimed(cls, user):
        return UserSubscription.objects.filter(user=user, plan__plan_type=PlanType.FREE_TRAIL).exists()



class SubscriptionPurchaseService:
    @classmethod
    @transaction.atomic
    def claim_free_trail(cls, user, trail_plan, billing_cycle, day):
        if SubscriptionValidationService.has_active_subscription(user):
            raise ValidationError({"detail": "You already have an active subscription."})
        now = timezone.now()
        expires_at = now + timedelta(days=day)
        subscription = UserSubscription.objects.create(
            user=user,
            plan=trail_plan,
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            expires_at=expires_at,
            next_billing_date=expires_at,
            auto_renew=False
        )
        return {"subscription": subscription, "message": "Free Trail Claim Successfully."}

    @classmethod
    @transaction.atomic
    def purchase(cls, user, plan, billing_cycle, organization=None):
        if SubscriptionValidationService.has_active_subscription(user):
            raise ValidationError({"detail": "You already have an active subscription."})

        now = timezone.now()
        if billing_cycle == BillingCycle.MONTHLY:
            expires_at = now + timedelta(days=30)
        elif billing_cycle == BillingCycle.YEARLY:
            expires_at = now + timedelta(days=365)
        else:
            raise ValidationError({"billing_cycle": "Invalid billing cycle."})

        subscription = UserSubscription.objects.create(
            user=user,
            organization=organization,
            plan=plan,
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.AWAITING_PAYMENT,
            start_date=now,
            expires_at=expires_at,
            next_billing_date=expires_at,
        )
        payment = Payment.objects.create(
            subscription=subscription,
            amount=plan.price,
            currency=plan.currency,
            status=PaymentStatus.PENDING,
        )
        return {"subscription": subscription, "payment": payment}


    

