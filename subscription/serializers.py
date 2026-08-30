from django.db import transaction
from django.utils import timezone
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
        return subscription