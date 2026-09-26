from rest_framework import serializers

from .choices import MessageTemplateType
from .models import StaticMessageTemplate


class WelcomeMessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticMessageTemplate
        fields = ("id", "subject", "message", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        user = self.context["request"].user
        organization = getattr(user, "organization", None)
        if not organization:
            raise serializers.ValidationError({"organization": "Create your business profile before setting a welcome message."})
        template, _ = StaticMessageTemplate.objects.update_or_create(
            organization=organization,
            user=user,
            template_type=MessageTemplateType.WELCOME,
            defaults={
                "subject": validated_data.get("subject", "Welcome Message"),
                "message": validated_data["message"],
                "is_active": validated_data.get("is_active", True),
                "is_default": False,
            },
        )
        return template

    def update(self, instance, validated_data):
        instance.subject = validated_data.get("subject", instance.subject)
        instance.message = validated_data.get("message", instance.message)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save(update_fields=["subject", "message", "is_active", "updated_at"])
        return instance