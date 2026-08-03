from rest_framework import serializers
from .models import (
    Organization, BusinessSetting, UserNotificationSettings, ProviderAccount, PhoneNumber, LocalVerification
)
from django.db import transaction

class OrganizationSetupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("name", "logo", "country", "business_type", "industry", "description", "website", "email", "business_hours")
    
    def validate(self, attrs):
        user = self.context["request"].user
        if hasattr(user, "organization"):
            raise serializers.ValidationError("Business profile already exists.")
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            user = self.context["request"].user
            organization = Organization.objects.create(
                owner=user,
                **validated_data,
            )
        
            # Auto Create Business Setting
            BusinessSetting.objects.create(
                organization=organization,
                user=user,
            )
            return organization

class UpdateBusinessSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessSetting
        fields = ("reply_tone", "auto_reply_enabled", "reply_speed", "auto_follow_up")

    def validate_reply_speed(self, value):
        if value < 0:
            raise serializers.ValidationError("Reply speed must be greater than or equal to 0.")
        return value

class OrganizationSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    lead_count = serializers.ReadOnlyField()
    has_phone_number = serializers.ReadOnlyField()
    has_business_hours = serializers.ReadOnlyField()

    class Meta:
        model = Organization
        fields = "__all__"
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["business_type"] = (instance.business_type.name if instance.business_type else None)
        data["industry"] = (instance.industry.name if instance.industry else None)
        return data
    
    def get_logo(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url

class ProviderAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderAccount
        fields = "__all__"

class LocalVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocalVerification
        fields = ("id", "is_verified", "complete_progress", "status", "messaging_service", "a2p_brand", "a2p_campaign",)

class PhoneNumberSerializer(serializers.ModelSerializer):
    verification = serializers.SerializerMethodField()
    verification_steps = serializers.SerializerMethodField()
    class Meta:
        model = PhoneNumber
        fields = "__all__"

    def get_verification(self, obj):
        verification, _ = LocalVerification.objects.get_or_create(
            phone_number=obj
        )
        return LocalVerificationSerializer(
            verification
        ).data

    def get_verification_steps(self, obj):
        verification, _ = LocalVerification.objects.get_or_create(phone_number=obj)
        return [

            {
                "title": "Messaging Service",
                "completed": verification.messaging_service is not None,
            },

            {
                "title": "A2P Brand",
                "completed": verification.a2p_brand is not None,
            },

            {
                "title": "A2P Campaign",
                "completed": verification.a2p_campaign is not None,
            },

        ]

class UserNotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationSettings
        fields = ("id", "all_notification", "push_notification_enabled", "email_alert_enabled", "sms_alert_enabled", "instant_lead_alert", "weekly_performance_report")
        read_only_fields = ("id",)

class NotificationToggleSerializer(serializers.Serializer):
    NOTIFICATION_FIELDS = (
        "push_notification_enabled",
        "email_alert_enabled",
        "sms_alert_enabled",
        "instant_lead_alert",
        "weekly_performance_report",
    )

    field = serializers.ChoiceField(choices=NOTIFICATION_FIELDS)
    value = serializers.BooleanField()




