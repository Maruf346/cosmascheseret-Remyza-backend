from rest_framework import serializers
from .models import BusinessType, Industry, FreeTrailPhoneNumber, UserFreeTrailNumber


class BusinessTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessType
        fields = ("id", "name", "slug", "description", "is_active", "sort_order")
        read_only_fields = ("id",)


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ("id", "name", "slug", "description", "is_active", "sort_order")
        read_only_fields = ("id",)





class SearchTrialNumberSerializer(serializers.Serializer):
    country = serializers.CharField(default="US")
    area_code = serializers.IntegerField(required=False)
    contains = serializers.CharField(required=False)
    limit = serializers.IntegerField(default=20)

class FreeTrailPhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreeTrailPhoneNumber
        # fields = "__all__"
        exclude = ("metadata",)

class SendSMSSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=20)
    body = serializers.CharField(max_length=1600)

    def validate_to(self, value):
        if not value.startswith("+"):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format. Example: +8801712345678"
            )
        return value