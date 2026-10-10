from rest_framework import serializers

from .choices import MessageTemplateType
from .models import StaticMessageTemplate
from .welcome_templates import WELCOME_MESSAGE_TEMPLATES, get_welcome_template, list_welcome_templates


class WelcomeTemplatePresetSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    subject = serializers.CharField()
    message = serializers.CharField()
    tone = serializers.CharField()


class WelcomeMessageSelectionSerializer(serializers.Serializer):
    template = serializers.ChoiceField(choices=[(key, value["label"]) for key, value in WELCOME_MESSAGE_TEMPLATES.items()])


class WelcomeMessageTemplateSerializer(serializers.ModelSerializer):
    template = serializers.SerializerMethodField()

    class Meta:
        model = StaticMessageTemplate
        fields = ("id", "template", "subject", "message", "is_active", "created_at", "updated_at")
        read_only_fields = fields

    def get_template(self, obj):
        for key, preset in WELCOME_MESSAGE_TEMPLATES.items():
            if obj.subject == preset["subject"] and obj.message == preset["message"]:
                return key
        return "custom_legacy"


class WelcomeMessagePresetListDataSerializer(serializers.Serializer):
    templates = WelcomeTemplatePresetSerializer(many=True)
    selected = WelcomeMessageTemplateSerializer(allow_null=True)


class WelcomeMessagePresetSingleDataSerializer(serializers.Serializer):
    template = WelcomeTemplatePresetSerializer()
    selected = WelcomeMessageTemplateSerializer(allow_null=True)


class WelcomeMessagePresetDataSerializer(serializers.Serializer):
    templates = WelcomeTemplatePresetSerializer(many=True, required=False)
    template = WelcomeTemplatePresetSerializer(required=False)
    selected = WelcomeMessageTemplateSerializer(allow_null=True)


class WelcomeMessagePresetResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = WelcomeMessagePresetDataSerializer()


class WelcomeMessagePresetListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = WelcomeMessagePresetListDataSerializer()


class WelcomeMessagePresetSingleResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = WelcomeMessagePresetSingleDataSerializer()


class WelcomeMessageSelectionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = WelcomeMessageTemplateSerializer()


def get_selected_welcome_template(user):
    organization = getattr(user, "organization", None)
    if not organization:
        return None
    return StaticMessageTemplate.objects.filter(
        organization=organization,
        user=user,
        template_type=MessageTemplateType.WELCOME,
    ).first()


def save_selected_welcome_template(user, template_key):
    organization = getattr(user, "organization", None)
    if not organization:
        raise serializers.ValidationError({"organization": "Create your business profile before selecting a welcome message."})

    preset = get_welcome_template(template_key)
    if not preset:
        raise serializers.ValidationError({"template": "Choose one of: professional, friendly, casual."})

    template, _ = StaticMessageTemplate.objects.update_or_create(
        organization=organization,
        user=user,
        template_type=MessageTemplateType.WELCOME,
        defaults={
            "subject": preset["subject"],
            "message": preset["message"],
            "is_active": True,
            "is_default": False,
        },
    )
    return template
