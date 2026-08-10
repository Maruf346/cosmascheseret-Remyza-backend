from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import request, status
from core.utils.views import BaseCreateAPIView, BaseGetAPIView, BasePatchAPIView
from core.utils.viewsets import OwnReadOnlyModelViewSet
from rest_framework.viewsets import GenericViewSet
from .serializers import (
    OrganizationSetupSerializer, UpdateBusinessSettingSerializer, OrganizationSerializer, UserNotificationSettingsSerializer, ProviderAccountSerializer, PhoneNumberSerializer,

    UserNotificationSettings, NotificationToggleSerializer
)
from .choices import OnboardingStep
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound
from core.permissions import IsClientUser
from rest_framework.decorators import action
from twilio.rest import Client
import os
from core.permissions import IsClientUser
from .models import ProviderAccount, BusinessSetting, PhoneNumber, Organization
from twilio_app.service.services import TwilioService, TwilioLocalVerificationService
from rest_framework.viewsets import GenericViewSet

class BusinessProfileSetupAPIView(BaseCreateAPIView):
    serializer_class = OrganizationSetupSerializer
    permission_classes = [IsAuthenticated, IsClientUser]

    def create_perform(self, serializer):
        with transaction.atomic():
            organization = serializer.save()
            organization.onboarding_step = OnboardingStep.ACCOUNT_CREATED
            organization.save(update_fields=["onboarding_step"])
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    "success": True,
                    "message": "Business profile created successfully.",
                    "data": OrganizationSetupSerializer(organization).data,
                }, status=status.HTTP_201_CREATED, headers=headers
            )

class BusinessSubAccountSetupAPIView(APIView):
    permission_classes = [IsClientUser]

    def get_organization_profile(self):
        user = self.request.user
        if hasattr(user, "organization"):
            return user.organization
        else:
            raise Exception("User have no organization.")

    def post(self, request, *args, **kwargs):
        user = request.user
        organization = self.get_organization_profile()
        twilio_service = TwilioService(user=user, organization=organization)
        provider_account = twilio_service.get_or_create_subaccount()
        return Response(
            {
                "success": True,
                "message": "Twilio sub-account setup successfully.",
                "data": ProviderAccountSerializer(provider_account).data
            }, status=status.HTTP_200_OK
        )
    
    # @transaction.atomic
    # def get(self, request, *args, **kwargs):
    #     data = request.data
    #     phone_type = data.get("phone_type", None)
    #     area_code = data.get("area_code", None)

    #     business_profile = self.get_organization_profile()
    #     twilio_service = TwilioService(business_profile)
    #     twilio_number = twilio_service.search_numbers(phone_type=phone_type, area_code=area_code)
    #     return Response({
    #         "success": True,
    #         "twilio_number": twilio_number
    #     })
    
    

    # @transaction.atomic
    # def post(self, request, *args, **kwargs):
    #     data = request.data
    #     parchase_number = data.get("parchase_number", None)
    #     phone_type = data.get("phone_type", None)

    #     organization = self.get_organization_profile()
    #     twilio_service = TwilioService(organization)
    #     provider_account = twilio_service.get_or_create_subaccount()
        
    #     if parchase_number:
    #         purchase_data = twilio_service.purchase_number(parchase_number)
    #         print("purchase_data: ", purchase_data)
    #         return Response(
    #             {
    #                 "success": True,
    #                 "message": f"{parchase_number} this number is successfully parchase."
    #             }, status=status.HTTP_201_CREATED
    #         )
    #     else:
    #         twilio_number = twilio_service.list_numbers(phone_type=phone_type)
    #         return Response(
    #             {
    #                 "success": True,
    #                 "message": "Parchase Number must be selected!",
    #                 "purchase_number": twilio_number
    #             }, status=status.HTTP_200_OK
    #         )

class BusinessSubAccountSyncAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClientUser]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            organization = user.organization
            twilio_service = TwilioService(user=user, organization=organization)
            provider_account, provider_account_serialize = twilio_service.sync_subaccount()
            return Response(
                {
                    "success": True,
                    "message": "Twilio sub-account synced successfully.",
                    "data": provider_account_serialize
                }, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": str(e),
                }, status=status.HTTP_400_BAD_REQUEST
            )

class BusinessPhoneNumberSetupAPIViewSets(GenericViewSet):
    permission_classes = [IsAuthenticated, IsClientUser]

    def get_phone_number(self) -> PhoneNumber:
        if getattr(self.get_organization_profile(), "phone_numbers", None) is None:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Phone Number not found."
                }
            )
        phone_number = self.get_organization_profile().phone_numbers.first()
        return phone_number

    @action(detail=False, methods=["get"], url_path="get")
    def phone_number_get(self, request):
        phone_number = self.get_phone_number()
        return Response(
            {
                "success": True,
                "data": PhoneNumberSerializer(phone_number).data,
            }, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"], url_path="verify-check")
    def phone_number_verification_check(self, request):
        verification = self.get_phone_number().local_verification
        data = [

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
        return Response(
            {
                "success": True,
                "data": data
            }, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], url_path="verify/step-01")
    def phone_verification_step_01(self, request):
        # try:
        phone_number = self.get_phone_number()
        local_verification = phone_number.local_verification
        verification_service = TwilioLocalVerificationService(
            user=self.request.user, phone_number=phone_number, organization=self.get_organization_profile()
        )

        data = request.data

        if local_verification.messaging_service:
            messaging_service = local_verification.messaging_service
        else:
            messaging_service = verification_service.attach_phone_number()

        if local_verification.a2p_brand:
            a2p_brand = local_verification.a2p_brand
        else:
            a2p_brand = verification_service.register_brand(data)
        

        local_verification.refresh_from_db()
        data = [
            {
                "title": "Messaging Service",
                "completed": local_verification.messaging_service is not None,
            },

            {
                "title": "A2P Brand",
                "completed": local_verification.a2p_brand is not None,
            },

            {
                "title": "A2P Campaign",
                "completed": local_verification.a2p_campaign is not None,
            },

        ]
        return Response(
            {
                "success": True,
                "data": data,
                "a2p_brand": a2p_brand,
                "policy": a2p_brand
            }, status=status.HTTP_200_OK
        )
        # except Exception as e:
        #     return Response(
        #         {
        #             "success": False,
        #             "message": str(e)
        #         }
        #     )
    
    def get_organization_profile(self) -> Organization:
        user = self.request.user
        if hasattr(user, "organization"):
            return user.organization
        else:
            raise Exception("User have no organization.")

    @action(detail=False, methods=["get"], url_path="search")
    def search_numbers(self, request):
        phone_type = request.query_params.get("phone_type", "local")
        area_code = request.query_params.get("area_code", None)

        organization = self.get_organization_profile()
        twilio_service = TwilioService(user=request.user, organization=organization)
        twilio_number = twilio_service.advanced_search_numbers(phone_type=phone_type, area_code=area_code)
        return Response({
            "success": True,
            "count": len(twilio_number),
            "twilio_number": twilio_number
        }, status=status.HTTP_200_OK)

    def check_phone_number_exists(self, request):
        if getattr(request.user, "organization", None) is None:
            raise ValidationError(
                {
                    "success": False,
                    "message": "User does not have an organization profile."
                }
            )
        elif not hasattr(request.user.organization, "provider_account"):
            raise ValidationError(
                {
                    "success": False,
                    "message": "User does not have a Twilio sub-account. Please set up a sub-account first."
                }
            )
        elif not request.user.organization.provider_account.status == "active":
            raise ValidationError(
                {
                    "success": False,
                    "message": "User's Twilio sub-account is not active. Please activate the sub-account first.",
                }
            )
        elif not request.user.organization.provider_account.account_sid:
            raise ValidationError(
                {
                    "success": False,
                    "message": "User's Twilio sub-account SID is missing. Please check the sub-account details.",
                }
            )
        elif getattr(request.user.organization.provider_account, "auth_token", None) is None:
            raise ValidationError(
                {
                    "success": False,
                    "message": "User's Twilio sub-account auth token is missing. Please check the sub-account details.",
                }
            )
        elif getattr(request.user.organization.provider_account, "phone_numbers", None) is not None:
            raise ValidationError(
                {
                    "success": False,
                    "message": "User's Twilio Phone Number already set up.",
                }
            )

    @action(detail=False, methods=["post"], url_path="purchase")
    def purchase_number(self, request):
        self.check_phone_number_exists(request)

        parchase_number = request.data.get("parchase_number", None)
        phone_type = request.data.get("phone_type", "local")

        organization = self.get_organization_profile()
        twilio_service = TwilioService(user=request.user, organization=organization)
        provider_account = twilio_service.get_or_create_subaccount()
        if parchase_number:
            purchase_data = twilio_service.purchase_number(parchase_number)
            return Response(
                {
                    "success": True,
                    "message": f"{parchase_number} this number is successfully purchased.",
                    "data": purchase_data
                }, status=status.HTTP_201_CREATED
            )
        else:
            twilio_number = twilio_service.advanced_search_numbers(phone_type=phone_type)
            return Response(
                {
                    "success": True,
                    "message": "Purchase Number must be selected!",
                    "purchase_numbers": twilio_number
                }, status=status.HTTP_200_OK
            )

    @action(detail=False, methods=["get"], url_path="sync")
    def sync_phone_number(self, request):
        phone_number = self.get_phone_number()
        twilio_sync_number = TwilioService(self.request.user, self.get_organization_profile()).sync(phone_number)
        return Response(
            {
                "success": True,
                "data": PhoneNumberSerializer(phone_number).data,
                "twilio_sync": twilio_sync_number
            }, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["patch"], url_path="webhook-update")
    def webhook_url_update(self, request):
        phone_number = self.get_phone_number()
        data = request.data
        # print("request.data: ", data)
        # payload = {
        #     "sms_url": data.get("sms_url", None),
        #     "sms_method": data.get("sms_method", None),
        #     "voice_url": data.get("voice_url", None),
        #     "voice_method": data.get("voice_method", None),
        #     "status_callback": data.get("status_callback", None),
        #     "status_callback_method": data.get("status_callback_method", None),
        #     "voice_fallback_url": data.get("voice_fallback_url", None),
        #     "voice_fallback_method": data.get("voice_fallback_method", None),
        #     "sms_fallback_url": data.get("sms_fallback_url", None),
        #     "sms_fallback_method": data.get("sms_fallback_method", None)
        # }
        twilio_number = TwilioService(self.request.user, self.get_organization_profile()).update_webhook(phone_number, data)
        return Response(
                    {
                "success": True,
                "message": "Twilio Webhook URL Update!",
                "data": PhoneNumberSerializer(phone_number).data,
                "twilio_sync": twilio_number
            }, status=status.HTTP_200_OK
        )



class UserBusinessProfileAPIView(APIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsClientUser]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            organization = user.organization
            serializer = self.serializer_class(organization, context={"request": request})

            response_data = {"business_profile": serializer.data}
            if getattr(organization, "provider_account", None):
                response_data["provider_account"] = ProviderAccountSerializer(organization.provider_account).data

            if getattr(organization, "phone_numbers", None):
                phone_number = organization.phone_numbers.first()
                response_data["phone_number"] = PhoneNumberSerializer(phone_number).data

            return Response(
                {
                    "success": True,
                    "data": response_data
                }, status=status.HTTP_200_OK
            )
        except AttributeError:
            raise NotFound("Business profile not found.", status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        user = request.user
        try:
            organization = user.organization
            serializer = self.serializer_class(organization, data=request.data, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()

            if getattr(organization, "provider_account", None):
                TwilioService(user=user, organization=organization).update_subaccount(friendly_name=organization.name)
            return Response(
                {
                    "success": True,
                    "message": "Business profile updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
        except AttributeError:
            raise NotFound("Business profile not found.", status.HTTP_404_NOT_FOUND)



class UserBusinessOnboardingAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClientUser]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            organization = user.organization
            return Response(
                {
                    "success": True,
                    "data": {
                        "onboarding_step": organization.onboarding_step,
                    }
                }, status=status.HTTP_200_OK
            )
        except AttributeError:
            raise NotFound("Business profile not found.", status.HTTP_404_NOT_FOUND)

class UserBusinessSettingAPIView(APIView):
    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            business_setting = BusinessSetting.objects.get(user=user)
            serializer = UpdateBusinessSettingSerializer(business_setting)
            return Response(
                {
                    "success": True,
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
        except BusinessSetting.DoesNotExist:
            raise NotFound("Business setting not found.", status.HTTP_404_NOT_FOUND)
    
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        user = request.user
        try:
            business_setting = BusinessSetting.objects.get(user=user)
            serializer = UpdateBusinessSettingSerializer(business_setting, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Business settings updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
        except BusinessSetting.DoesNotExist:
            raise NotFound("Business setting not found.", status.HTTP_404_NOT_FOUND)

class UserNotificationSettingsViewSet(GenericViewSet):
    serializer_class = UserNotificationSettingsSerializer
    permission_classes = [IsAuthenticated, IsClientUser]

    def get_object(self):
        organization = self.request.user.organization
        if organization:
            user_notification, _ = UserNotificationSettings.objects.get_or_create(
                user=self.request.user, organization=organization
            )
        else:
            user_notification, _ = UserNotificationSettings.objects.get_or_create(
                user=self.request.user
            )
        return user_notification

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        serializer = self.get_serializer(self.get_object())
        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )

    @action(detail=False, methods=["patch"], url_path="all-notification")
    def update_all_notification(self, request):
        setting = self.get_object()
        serializer = self.get_serializer(setting, data=request.data)
        serializer.is_valid(raise_exception=True)
        all_notification = serializer.validated_data.get("all_notification")
        
        setting.all_notification = all_notification
        setting.push_notification_enabled = all_notification
        setting.email_alert_enabled = all_notification
        setting.sms_alert_enabled = all_notification
        setting.instant_lead_alert = all_notification
        setting.weekly_performance_report = all_notification
        setting.save()

        return Response(
            {
                "success": True,
                "message": "Notification settings updated.",
                "data": self.get_serializer(setting).data,
            }
        )

    @action(detail=False, methods=["patch"], url_path="toggle")
    def toggle(self, request):
        serializer = NotificationToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        field = serializer.validated_data["field"]
        value = serializer.validated_data["value"]

        setting = self.get_object()

        setattr(setting, field, value)

        setting.all_notification = all([
            setting.push_notification_enabled,
            setting.email_alert_enabled,
            setting.sms_alert_enabled,
            setting.instant_lead_alert,
            setting.weekly_performance_report,
        ])

        setting.save()

        return Response(
            {
                "success": True,
                "message": f"{field} updated successfully.",
                "data": self.get_serializer(setting).data,
            },
            status=status.HTTP_200_OK,
        )


