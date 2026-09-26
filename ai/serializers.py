from rest_framework import serializers


class StructuredMessageRequestSerializer(serializers.Serializer):
    tone = serializers.CharField(max_length=50)
    msg = serializers.CharField()

    def validate_tone(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Tone is required.")
        return value

    def validate_msg(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message is required.")
        return value


class StructuredMessageResponseSerializer(serializers.Serializer):
    tone = serializers.CharField()
    structured_msg = serializers.CharField()