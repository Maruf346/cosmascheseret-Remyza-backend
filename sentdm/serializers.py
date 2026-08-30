from rest_framework import serializers

from .choices import SentDMChannel
from .models import SentDMMessage, SentDMProfile, SentDMWebhookEvent


class SentDMAccountCheckSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = serializers.DictField()
    meta = serializers.DictField(required=False)


class SentDMProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentDMProfile
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SentDMMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentDMMessage
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SentDMWebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentDMWebhookEvent
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SentDMProfileCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    short_name = serializers.CharField(required=False, allow_blank=True, max_length=20)
    description = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class SentDMProfileCompleteSerializer(serializers.Serializer):
    profile_id = serializers.CharField(required=False, allow_blank=True)


class SentDMSendSandboxMessageSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=30)
    text = serializers.CharField()
    profile_id = serializers.CharField(required=False, allow_blank=True)
    channel = serializers.ChoiceField(choices=SentDMChannel.choices, default=SentDMChannel.AUTO)

    def validate_to(self, value):
        if not value.startswith("+"):
            raise serializers.ValidationError("Phone number must be in E.164 format, for example +15551234567.")
        return value

