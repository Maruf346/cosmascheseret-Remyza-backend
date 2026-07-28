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
    type = serializers.CharField(required=False)

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

from rest_framework import serializers

from .choices import (
    OptInType,
    UseCaseCategory,
    BusinessType,
)


class TollFreeVerificationSubmitSerializer(serializers.Serializer):
    # Business Information
    business_name = serializers.CharField(max_length=255)
    doing_business_as = serializers.CharField(max_length=255, required=False, allow_blank=True)
    business_website = serializers.URLField()
    notification_email = serializers.EmailField()
    business_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_registration_authority = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_registration_country = serializers.CharField(max_length=10, required=False, allow_blank=True)
    business_registration_phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    business_type = serializers.ChoiceField(choices=BusinessType.choices)

    # Use Case
    use_case_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=UseCaseCategory.choices),
        allow_empty=False,
    )

    use_case_summary = serializers.CharField()
    production_message_sample = serializers.CharField()
    message_volume = serializers.IntegerField(min_value=1)
    additional_information = serializers.CharField(required=False, allow_blank=True)

    # Opt-In
    opt_in_type = serializers.ChoiceField(choices=OptInType.choices)
    opt_in_image_urls = serializers.ListField(child=serializers.URLField(), default=list,)
    opt_in_confirmation_message = serializers.CharField(required=False, allow_blank=True)

    opt_in_keywords = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)

    # Compliance
    help_message_sample = serializers.CharField()
    privacy_policy_url = serializers.URLField()
    terms_and_conditions_url = serializers.URLField(required=False, allow_blank=True)
    age_gated_content = serializers.BooleanField(default=False)

    # Optional Vetting
    vetting_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    vetting_provider = serializers.CharField(max_length=255, required=False, allow_blank=True)

    # Validation
    def validate_production_message_sample(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError(
                "Provide a more realistic message sample."
            )
        return value
    
    def validate_help_message_sample(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError(
                "Provide a more realistic help message sample."
            )
        return value

    def validate_message_volume(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Message volume must be greater than zero."
            )
        return value

    def validate_use_case_categories(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate use case categories are not allowed."
            )
        return value

    def validate_opt_in_image_urls(self, value):
        if len(value) > 5:
            raise serializers.ValidationError(
                "Maximum 5 opt-in image URLs are allowed."
            )
        return value

    def validate_opt_in_keywords(self, value):
        if len(value) > 20:
            raise serializers.ValidationError(
                "Maximum 20 opt-in keywords are allowed."
            )
        return value

    def validate(self, attrs):
        opt_in_type = attrs.get("opt_in_type")

        if (
            opt_in_type in [
                OptInType.WEB_FORM,
                OptInType.PAPER_FORM,
                OptInType.MOBILE_QR_CODE,
            ]
            and not attrs.get("opt_in_image_urls")
        ):
            raise serializers.ValidationError(
                {
                    "opt_in_image_urls": (
                        "At least one opt-in image URL is required "
                        "for the selected opt-in type."
                    )
                }
            )

        if opt_in_type == OptInType.TEXT and not attrs.get("opt_in_keywords"):
            raise serializers.ValidationError(
                {
                    "opt_in_keywords": (
                        "Opt-in keywords are required when using TEXT opt-in."
                    )
                }
            )

        if opt_in_type == OptInType.VERBAL and not attrs.get("opt_in_confirmation_message"):
            raise serializers.ValidationError(
                {
                    "opt_in_confirmation_message": (
                        "Verbal consent script is required for VERBAL opt-in."
                    )
                }
            )
        return attrs
