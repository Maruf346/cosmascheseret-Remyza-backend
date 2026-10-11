from django.db import transaction
from django.utils import timezone
from notifications.services import NotificationTemplates, safe_notify
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .choices import PaymentMediumChoices, StoreEnvironmentChoices
from .models import UserSubscription


class UserSubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = (
            "id",
            "uuid",
            "user",
            "organization",
            "product_id",
            "plan_type",
            "medium",
            "purchase_token",
            "transaction_id",
            "original_transaction_id",
            "order_id",
            "store_environment",
            "store_status",
            "is_subscription_active",
            "purchase_date",
            "expiry_date",
            "amount",
            "currency_code",
            "verification_payload",
            "app_bundle_id",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "uuid", "user", "organization", "app_bundle_id", "is_active", "created_at", "updated_at")

    def validate_medium(self, value):
        if value not in PaymentMediumChoices.values:
            raise serializers.ValidationError("medium must be either 'apple' or 'google'.")
        return value

    def validate_store_environment(self, value):
        if value and value not in StoreEnvironmentChoices.values:
            raise serializers.ValidationError("store_environment must be either 'production' or 'sandbox'.")
        return value

    def validate(self, attrs):
        medium = attrs.get("medium")
        if medium == PaymentMediumChoices.GOOGLE and not attrs.get("purchase_token"):
            raise serializers.ValidationError({"purchase_token": "purchase_token is required for Google purchases."})

        if medium == PaymentMediumChoices.APPLE and not (
            attrs.get("transaction_id") or attrs.get("original_transaction_id")
        ):
            raise serializers.ValidationError(
                {"transaction_id": "transaction_id or original_transaction_id is required for Apple purchases."}
            )

        return attrs

    @extend_schema_field(serializers.BooleanField())
    def get_is_active(self, obj):
        return obj.is_active

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        organization = getattr(user, "organization", None)
        now = timezone.now()
        subscription = UserSubscription.objects.create(
            user=user,
            organization=organization,
            start_date=validated_data.get("purchase_date") or now,
            expires_at=validated_data.get("expiry_date"),
            status="active" if validated_data.get("is_subscription_active") else "awaiting_payment",
            **validated_data,
        )
        transaction.on_commit(lambda: safe_notify(NotificationTemplates.subscription_recorded, subscription))
        return subscription


class UserSubscriptionListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = UserSubscriptionSerializer(many=True)


class AdminMetricSerializer(serializers.Serializer):
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    change_percent = serializers.FloatField()


class AdminCountMetricSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    change_percent = serializers.FloatField()


class AdminSubscriptionSummarySerializer(serializers.Serializer):
    total_revenue = AdminMetricSerializer()
    active_subscribers = AdminCountMetricSerializer()
    trial_users = AdminCountMetricSerializer()
    suspended_users = AdminCountMetricSerializer()


class AdminSubscriberListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    profile_pic = serializers.CharField(allow_blank=True, allow_null=True)
    plan = serializers.CharField()
    billing = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    joined_at = serializers.DateTimeField()


class AdminSubscriberListDataSerializer(serializers.Serializer):
    summary = AdminSubscriptionSummarySerializer()
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminSubscriberListItemSerializer(many=True)


class AdminSubscriberListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminSubscriberListDataSerializer()


class AdminSubscriberDetailSerializer(AdminSubscriberListItemSerializer):
    phone_number = serializers.CharField()
    status = serializers.CharField()
    next_billing_cycle = serializers.DateTimeField(allow_null=True)
    lifetime_spent = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    subscription_id = serializers.IntegerField(allow_null=True)
    product_id = serializers.CharField(allow_blank=True)
    store_status = serializers.CharField(allow_blank=True)
    subscription_started_at = serializers.DateTimeField(allow_null=True)
    subscription_expires_at = serializers.DateTimeField(allow_null=True)


class AdminSubscriberDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminSubscriberDetailSerializer()


class AdminMonthlyRevenueItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    year = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()


class AdminMonthlyRevenueResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminMonthlyRevenueItemSerializer(many=True)


class AdminRevenueAnalyticsSummarySerializer(serializers.Serializer):
    new_users = AdminCountMetricSerializer()
    revenue = AdminMetricSerializer()
    messages_sent = AdminCountMetricSerializer()
    lead_conversion_percent = AdminMetricSerializer()


class AdminMessageVolumeItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    message_volume = serializers.IntegerField()


class AdminSubscriberBreakdownItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField()
    percent = serializers.FloatField()


class AdminLeadBreakdownItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField()
    percent = serializers.FloatField()
    change_percent = serializers.FloatField(required=False)


class AdminRevenueAnalyticsDataSerializer(serializers.Serializer):
    period = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    summary = AdminRevenueAnalyticsSummarySerializer()
    message_volume_analytics = AdminMessageVolumeItemSerializer(many=True)
    subscribers = AdminSubscriberBreakdownItemSerializer(many=True)
    leads = AdminLeadBreakdownItemSerializer(many=True)


class AdminRevenueAnalyticsResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminRevenueAnalyticsDataSerializer()


class AdminUserAnalyticsSummarySerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_leads_captured = serializers.IntegerField()


class AdminUserRatioItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    year = serializers.IntegerField()
    users = serializers.IntegerField()


class AdminUserAnalyticsDataSerializer(serializers.Serializer):
    summary = AdminUserAnalyticsSummarySerializer()
    year = serializers.IntegerField()
    user_ratio = AdminUserRatioItemSerializer(many=True)


class AdminUserAnalyticsResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminUserAnalyticsDataSerializer()
