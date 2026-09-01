from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import (
    Organization, BusinessSetting, UserNotificationSettings, ProviderAccount, PhoneNumber
)
from twilio_app.models import (
    LocalVerification
)
from django.db import transaction
SENTDM_WHATSAPP_FIELDS = (
    "sentdm_whatsapp_waba_id",
    "sentdm_whatsapp_phone_number_id",
    "sentdm_whatsapp_access_token",
)


def validate_sentdm_whatsapp_config(attrs, instance=None):
    values = {
        field: str(attrs.get(field, getattr(instance, field, "")) or "").strip()
        for field in SENTDM_WHATSAPP_FIELDS
    }
    provided_fields = [field for field, value in values.items() if value]
    if 0 < len(provided_fields) < len(SENTDM_WHATSAPP_FIELDS):
        missing_fields = [field for field, value in values.items() if not value]
        raise serializers.ValidationError(
            {
                "sentdm_whatsapp": "To connect a dedicated WhatsApp Business Account, waba_id, phone_number_id, and access_token are all required. Leave all three blank to skip WhatsApp.",
                "missing_fields": missing_fields,
            }
        )
    return attrs

class OrganizationSetupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "name", "logo", "country", "business_type", "industry", "description", "website", "email", "business_hours",
            "sentdm_legal_name", "sentdm_tax_id", "sentdm_vertical", "sentdm_authorized_rep_name",
            "sentdm_authorized_rep_title", "sentdm_authorized_rep_email", "sentdm_authorized_rep_phone",
            "sentdm_support_email", "sentdm_support_phone", "sentdm_privacy_policy_url", "sentdm_terms_url",
            "sentdm_opt_in_url", "sentdm_opt_in_description", "sentdm_messaging_use_case",
            "sentdm_messaging_use_case_us",
            "sentdm_sample_message_1", "sentdm_sample_message_2", "sentdm_sample_message_3",
            "sentdm_opt_in_confirmation_message", "sentdm_opt_out_confirmation_message",
            "sentdm_help_response_message", "sentdm_expected_daily_volume",
            "sentdm_whatsapp_waba_id", "sentdm_whatsapp_phone_number_id", "sentdm_whatsapp_access_token",
        )
        extra_kwargs = {"sentdm_whatsapp_access_token": {"write_only": True, "required": False}}
    
    def validate(self, attrs):
        attrs = validate_sentdm_whatsapp_config(attrs)
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
    lead_count = serializers.IntegerField(read_only=True)
    has_phone_number = serializers.BooleanField(read_only=True)
    has_business_hours = serializers.BooleanField(read_only=True)

    class Meta:
        model = Organization
        fields = "__all__"
        extra_kwargs = {"sentdm_whatsapp_access_token": {"write_only": True, "required": False}}
    
    def validate(self, attrs):
        return validate_sentdm_whatsapp_config(attrs, instance=self.instance)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("sentdm_whatsapp_access_token", None)
        data["has_sentdm_whatsapp_config"] = all(
            str(getattr(instance, field, "") or "").strip()
            for field in SENTDM_WHATSAPP_FIELDS
        )
        data["business_type"] = (instance.business_type.name if instance.business_type else None)
        data["industry"] = (instance.industry.name if instance.industry else None)
        return data
    
    @extend_schema_field(serializers.CharField(allow_null=True))
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




