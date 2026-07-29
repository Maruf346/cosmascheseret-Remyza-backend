from rest_framework import serializers
from .models import BusinessType, Industry, FreeTrailPhoneNumber, UserFreeTrailNumber, TollFreeVerification
from .choices import (
    OptInType,
    UseCaseCategory,
    BusinessTypeChoice, BusinessRegistrationAuthority, 
)

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


class TollFreeVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TollFreeVerification
        fields = "__all__"


from rest_framework import serializers

from .choices import (
    BusinessTypeChoice,
    OptInType,
    UseCaseCategory,
)


class TollFreeVerificationSubmitSerializer(serializers.Serializer):
    # Twilio -----
    customer_profile_sid = serializers.CharField(max_length=64, required=False, allow_blank=True)
    external_reference_id = serializers.CharField(max_length=255, required=False, allow_blank=True)

    # Business Information -----
    business_name = serializers.CharField(max_length=255)
    doing_business_as = serializers.CharField(max_length=255, required=False, allow_blank=True)
    business_website = serializers.URLField()
    notification_email = serializers.EmailField()

    business_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_registration_authority = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_registration_country = serializers.CharField(max_length=10, required=False, allow_blank=True)
    business_registration_phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    business_type = serializers.ChoiceField(choices=BusinessTypeChoice.choices)

    # Business Address -----
    business_street_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    business_street_address2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    business_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_state_province_region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_postal_code = serializers.CharField(max_length=30, required=False, allow_blank=True)
    business_country = serializers.CharField(max_length=10, required=False, allow_blank=True)

    # Business Contact -----
    business_contact_first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_contact_last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    business_contact_email = serializers.EmailField(required=False, allow_blank=True)
    business_contact_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    # Use Case -----
    use_case_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=UseCaseCategory.choices),
        allow_empty=False,
    )
    use_case_summary = serializers.CharField()
    production_message_sample = serializers.CharField()
    message_volume = serializers.CharField(max_length=10)
    additional_information = serializers.CharField(required=False, allow_blank=True)

    # Opt-In -----
    opt_in_type = serializers.ChoiceField(choices=OptInType.choices)
    opt_in_image_urls = serializers.ListField(child=serializers.URLField(), required=False, default=list)
    opt_in_confirmation_message = serializers.CharField(required=False, allow_blank=True)
    opt_in_keywords = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)

    # Compliance -----
    help_message_sample = serializers.CharField()
    privacy_policy_url = serializers.URLField()
    terms_and_conditions_url = serializers.URLField(required=False, allow_blank=True)
    age_gated_content = serializers.BooleanField(default=False)

    # Vetting -----
    vetting_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    vetting_provider = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_customer_profile_sid(self, value):
        if not value.startswith("BU"):
            raise serializers.ValidationError(
                "Invalid Customer Profile SID."
            )
        return value

    # # Validation
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
        volume = value.replace(",", "")
        if int(volume) <= 0:
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

    def get_payload(self, phone_number):
        payload = {
            # "CustomerProfileSid": self.validated_data.get("customer_profile_sid") or phone_number.customer_profile_sid,

            "business_name": self.validated_data["business_name"],
            "doing_business_as": self.validated_data.get("doing_business_as", ""),
            "business_website": self.validated_data["business_website"],
            "notification_email": self.validated_data["notification_email"],
            "business_registration_number": self.validated_data.get("business_registration_number", ""),
            "business_registration_authority": self.validated_data.get("business_registration_authority", ""),
            "business_registration_country": self.validated_data.get("business_registration_country", ""),
            "business_registration_phone_number": self.validated_data.get("business_registration_phone_number", ""),
            "business_type": self.validated_data["business_type"],

            "business_street_address": self.validated_data.get("business_street_address", ""),
            "business_street_address2": self.validated_data.get("business_street_address2", ""),
            "business_city": self.validated_data.get("business_city", ""),
            "business_state_province_region": self.validated_data.get("business_state_province_region", ""),
            "business_postal_code": self.validated_data.get("business_postal_code", ""),
            "business_country": self.validated_data.get("business_country", ""),

            "business_contact_first_name": self.validated_data.get("business_contact_first_name", ""),
            "business_contact_last_name": self.validated_data.get("business_contact_last_name", ""),
            "business_contact_email": self.validated_data.get("business_contact_email", ""),
            "business_contact_phone": self.validated_data.get("business_contact_phone", ""),

            "use_case_categories": self.validated_data["use_case_categories"],
            "use_case_summary": self.validated_data["use_case_summary"],
            "production_message_sample": self.validated_data["production_message_sample"],
            "message_volume": str(self.validated_data["message_volume"]),
            "additional_information": self.validated_data.get("additional_information", ""),

            "opt_in_type": self.validated_data["opt_in_type"],
            "opt_in_image_urls": self.validated_data.get("opt_in_image_urls", []),
            "opt_in_confirmation_message": self.validated_data.get("opt_in_confirmation_message", ""),
            "opt_in_keywords": self.validated_data.get("opt_in_keywords", []),

            "help_message_sample": self.validated_data["help_message_sample"],
            "privacy_policy_url": self.validated_data["privacy_policy_url"],
            "terms_and_conditions_url": self.validated_data.get("terms_and_conditions_url", ""),
            "age_gated_content": self.validated_data.get("age_gated_content", False),

            "tollfree_phone_number_sid": phone_number.provider_phone_sid,

            # "ExternalReferenceId": self.validated_data.get("external_reference_id", ""),
            # "vetting_id": self.validated_data.get("vetting_id", ""),
            # "vetting_provider": self.validated_data.get("vetting_provider", ""),
        }

        payload = {
            k: v
            for k, v in payload.items()
            if v not in ("", None, [], {})
        }
        return payload



