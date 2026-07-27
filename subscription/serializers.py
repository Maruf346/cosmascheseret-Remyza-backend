from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription
from django.utils import timezone
from .choices import (
    PurchasePlatform
)

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "name", "description", "plan_type", "billing_type", "price", "currency", "trial_days", "sms_limit", "lead_limit", "ai_reply_limit", "custom_welcome_message", "ai_auto_reply", "lead_scoring", "advanced_analytics", "bulk_import", "ai_token_limit", "phone_number_limit", "knowledge_document_limit", "storage_limit", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")




class PurchaseSubscriptionSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()

    def validate_plan_id(self, value):
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Subscription plan not found.")
        self.context["plan"] = plan
        return value

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "name", "description", "plan_type", "billing_type", "price", "currency", "trial_days", "sms_limit", "lead_limit", "ai_reply_limit", "phone_number_limit", "knowledge_document_limit", "storage_limit", "custom_welcome_message", "ai_auto_reply", "lead_scoring", "advanced_analytics", "bulk_import")

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    payment_status = serializers.SerializerMethodField()
    invoice_status = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = ("id", "uuid", "plan", "status", "billing_cycle", "start_date", "expires_at", "next_billing_date", "auto_renew", "cancelled_at", "expires_at", "payment_status", "invoice_status", "days_remaining", "is_active", "created_at", "updated_at")

    def get_payment_status(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        return payment.status if payment else None

    def get_invoice_status(self, obj):
        invoice = obj.invoices.order_by("-created_at").first()
        return invoice.status if invoice else None

    def get_days_remaining(self, obj):
        if not obj.expires_at:
            return None
        remaining = obj.expires_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return 0
        return remaining.days

    def get_is_active(self, obj):
        now = timezone.now()
        return obj.status == "ACTIVE" and obj.expires_at and obj.expires_at > now

class VerifyPurchaseSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=PurchasePlatform.choices)
    subscription_plan_uuid = serializers.CharField(required=True)
    transaction_id = serializers.CharField(required=False)
    product_id = serializers.CharField(required=False)
    purchase_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    receipt_data = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    package_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_subscription_plan_uuid(self, value):
        subscription = UserSubscription.objects.get(uuid=value)
        if subscription:
            return subscription
        else: raise serializers.ValidationError("User Subscription not found.")

    # def validate(self, attrs):
    #     platform = attrs["platform"]
    #     if platform == PURCHASE_PLATFORM.ANDROID:
    #         if not attrs.get("purchase_token"):
    #             raise serializers.ValidationError({
    #                 "purchase_token": "Required for Android."
    #             })
    #     elif platform == PURCHASE_PLATFORM.IOS:
    #         if not attrs.get("receipt_data"):
    #             raise serializers.ValidationError({
    #                 "receipt_data": "Required for iOS."
    #             })
    #     return attrs
