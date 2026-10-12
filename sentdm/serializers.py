from rest_framework import serializers

from .choices import SentDMChannel
from .models import SentDMCampaign, SentDMMessage, SentDMProfile, SentDMWebhookEvent


class SentDMAccountCheckSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = serializers.DictField()
    meta = serializers.DictField(required=False)


class SentDMProfileSerializer(serializers.ModelSerializer):
    is_agent_whatsapp_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = SentDMProfile
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "is_agent_whatsapp_active")


class SentDMMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentDMMessage
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class AdminMessageUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    profile_pic = serializers.CharField(allow_blank=True, allow_null=True)
    is_chesera_user = serializers.BooleanField()


class AdminMessageContactSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)


class AdminMessageSummarySerializer(serializers.Serializer):
    total_messages = serializers.IntegerField()
    delivered_or_sent_messages = serializers.IntegerField()
    failed_messages = serializers.IntegerField()


class AdminMessageListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user = AdminMessageUserSerializer()
    contact = AdminMessageContactSerializer()
    receiver = AdminMessageContactSerializer()
    message = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    direction = serializers.CharField()
    timestamp = serializers.DateTimeField()
    conversation_id = serializers.IntegerField(allow_null=True)


class AdminMessageListDataSerializer(serializers.Serializer):
    summary = AdminMessageSummarySerializer()
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminMessageListItemSerializer(many=True)


class AdminMessageListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminMessageListDataSerializer()


class AdminMessageDetailSerializer(AdminMessageListItemSerializer):
    from_user = AdminMessageUserSerializer()
    to = AdminMessageContactSerializer()
    content = serializers.CharField(allow_blank=True)
    metadata = serializers.JSONField()
    channel = serializers.CharField()
    sent_message_id = serializers.CharField(allow_blank=True)


class AdminMessageDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminMessageDetailSerializer()


class AdminConversationMessageItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender = AdminMessageUserSerializer()
    receiver = AdminMessageContactSerializer()
    message = serializers.CharField(allow_blank=True)
    timestamp = serializers.DateTimeField()
    status = serializers.JSONField()
    direction = serializers.CharField()
    metadata = serializers.JSONField()


class AdminConversationMessagesDataSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    chesera_user = AdminMessageUserSerializer()
    receiver = AdminMessageContactSerializer()
    total_messages = serializers.IntegerField()
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminConversationMessageItemSerializer(many=True)


class AdminConversationMessagesResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = AdminConversationMessagesDataSerializer()


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


class SentDMWhatsAppConnectSerializer(serializers.Serializer):
    profile_id = serializers.CharField(required=False, allow_blank=True)
    waba_id = serializers.CharField(max_length=100)
    phone_number_id = serializers.CharField(max_length=100)
    access_token = serializers.CharField(write_only=True)


class SentDMWhatsAppConfigSerializer(serializers.Serializer):
    profile_id = serializers.CharField(allow_blank=True)
    waba_id = serializers.CharField(allow_blank=True)
    phone_number_id = serializers.CharField(allow_blank=True)
    access_token = serializers.CharField(allow_blank=True)


class SentDMWhatsAppConfigResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = SentDMWhatsAppConfigSerializer()


class SentDMCurrentProfileResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = SentDMProfileSerializer()


class SentDMProfileSyncDataSerializer(serializers.Serializer):
    profile = SentDMProfileSerializer()
    sentdm_response = serializers.JSONField()


class SentDMProfileSyncResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = SentDMProfileSyncDataSerializer()


class SentDMProfileActionDataSerializer(serializers.Serializer):
    profile = SentDMProfileSerializer(allow_null=True)
    sentdm_response = serializers.JSONField()


class SentDMProfileActionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    sandbox = serializers.BooleanField(required=False)
    data = SentDMProfileActionDataSerializer()


class SentDMProfileCompleteSerializer(serializers.Serializer):
    profile_id = serializers.CharField(required=False, allow_blank=True)


class SentDMCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentDMCampaign
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SentDMComplianceReadinessSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    missing_fields = serializers.ListField(child=serializers.CharField())
    messages = serializers.DictField(child=serializers.CharField())
    profile_id = serializers.CharField(allow_blank=True)
    sample_message_count = serializers.IntegerField()
    messaging_use_case_us = serializers.CharField(allow_blank=True)


class SentDMCampaignCreateSerializer(serializers.Serializer):
    profile_id = serializers.CharField(required=False, allow_blank=True)
    campaign_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    campaign_type = serializers.CharField(required=False, allow_blank=True, max_length=50, default="App")


class SentDMSendSandboxMessageSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=30)
    text = serializers.CharField()
    profile_id = serializers.CharField(required=False, allow_blank=True)
    channel = serializers.ChoiceField(choices=SentDMChannel.choices, default=SentDMChannel.AUTO)

    def validate_to(self, value):
        if not value.startswith("+"):
            raise serializers.ValidationError("Phone number must be in E.164 format, for example +15551234567.")
        return value


class SentDMSendMessageSerializer(SentDMSendSandboxMessageSerializer):
    pass
