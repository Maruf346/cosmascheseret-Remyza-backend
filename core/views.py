from rest_framework.viewsets import ModelViewSet
from core.utils.viewsets import OwnModelViewSet
from .models import BusinessType, Industry
from .permissions import AdminWritePermission
from .serializers import (
    BusinessTypeSerializer,
    IndustrySerializer,
)


class BusinessTypeViewSet(OwnModelViewSet):
    serializer_class = BusinessTypeSerializer
    permission_classes = [AdminWritePermission]
    queryset = BusinessType.objects.filter(is_active=True).order_by("sort_order", "name")


class IndustryViewSet(OwnModelViewSet):
    serializer_class = IndustrySerializer
    permission_classes = [AdminWritePermission]
    queryset = Industry.objects.filter(is_active=True).order_by("sort_order", "name")




from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import (
    TwilioConfiguration,
    FreeTrailPhoneNumber,
    UserFreeTrailNumber,
)

from core.utils.viewsets import OwnReadOnlyModelViewSet
from .serializers import FreeTrailPhoneNumberSerializer, SearchTrialNumberSerializer, SendSMSSerializer
from .models import TwilioWebhookLog
from twilio.rest import Client
import os
import logging
logger = logging.getLogger(__name__)
from business.choices import PhoneNumberStatus
from twilio.base.exceptions import TwilioRestException
import json
from django.shortcuts import render
from rest_framework.exceptions import ValidationError

class FreeTrailPhoneNumberViewSet(OwnReadOnlyModelViewSet):
    serializer_class = FreeTrailPhoneNumberSerializer
    queryset = (FreeTrailPhoneNumber.objects.select_related().order_by("phone_number"))

    FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
    FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")

    MASTER_ACCOUNT_SID = os.getenv("ACCOUNT_SID")
    MASTER_AUTH_TOKEN = os.getenv("AUTH_TOKEN")
    
    # All Available Trial Number---
    @action(detail=False, methods=["get"])
    def available(self, request):
        queryset = self.get_queryset().filter(status=PhoneNumberStatus.ACTIVE, is_used=False)
        return Response(
            {
                "success": True,
                "count": len(queryset),
                "results": self.get_serializer(queryset, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


    # Search Available number in Twilio---
    def serialize_search_phone_number(self, number):
        return {
            "friendly_name": number.friendly_name,
            "phone_number": number.phone_number,
            "lata": getattr(number, "lata", None),
            "rate_center": getattr(number, "rate_center", None),
            "region": getattr(number, "region", None),
            "postal_code": getattr(number, "postal_code", None),
            "locality": getattr(number, "locality", None),
            "iso_country": getattr(number, "iso_country", None),
            "capabilities": number.capabilities,
            "address_requirements": number.address_requirements,
        }

    @action(detail=False, methods=["get"], url_path="search-number")
    def search_number(self, request):
        serializer = SearchTrialNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        country=serializer.validated_data.get("country", "US")
        # area_code=serializer.validated_data.get("area_code"),
        # contains=serializer.validated_data.get("contains"),
        # limit=serializer.validated_data.get("limit"),

        FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
        FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")
        client = Client(FREE_TRAIL_ACCOUNT_SID, FREE_TRAIL_AUTH_TOKEN)
        resource = client.available_phone_numbers(country).toll_free
        # resource = client.available_phone_numbers(country).local
        numbers = resource.list(limit=2, sms_enabled=True)
        numbers_list = [
            self.serialize_search_phone_number(number)
            for number in numbers
        ]

        return Response(
            {
                "success": True,
                "count": len(numbers_list),
                "results": numbers_list,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="check-availability")
    def check_availability(self, request):
        data = request.data
        last_4_digit = data.get("last_4_digit", None)
        if last_4_digit is None:
            return Response(
                {
                    "success": False,
                    "message": "Submit Must be last 4 digit of number."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
        FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")
        client = Client(FREE_TRAIL_ACCOUNT_SID, FREE_TRAIL_AUTH_TOKEN)
        resource = client.available_phone_numbers("US").toll_free.list(limit=2, sms_enabled=True, contains=last_4_digit)
        numbers_list = [
            self.serialize_search_phone_number(number)
            for number in resource
        ]
        return Response(
            {
                "success": True,
                "count": len(numbers_list),
                "results": numbers_list,
            },
            status=status.HTTP_200_OK,
        )


    # Purchase Number from Twilio---
    def serialize_purchase_phone_number(self, phone):
        return {
            "sid": getattr(phone, "sid", None),
            "account_sid": getattr(phone, "account_sid", None),
            "friendly_name": getattr(phone, "friendly_name", None),
            "phone_number": getattr(phone, "phone_number", None),
            "country_code": getattr(phone, "iso_country", None),
            "capabilities": getattr(phone, "capabilities", {}),
            "voice_url": getattr(phone, "voice_url", None),
            "sms_url": getattr(phone, "sms_url", None),
            "status_callback": getattr(phone, "status_callback", None),
            "address_requirements": getattr(phone, "address_requirements", None),
            "date_created": getattr(phone, "date_created", None),
            "date_updated": getattr(phone, "date_updated", None),
            "uri": getattr(phone, "uri", None),
        }
    
    def to_dict(self, phone):
        return {
            "sid": phone.sid,
            "account_sid": phone.account_sid,
            "phone_number": phone.phone_number,
            "friendly_name": phone.friendly_name,
            "status": phone.status,
            "type": phone.type,
            "origin": phone.origin,
            "capabilities": phone.capabilities,
            "sms_url": phone.sms_url,
            "voice_url": phone.voice_url,
            "sms_method": phone.sms_method,
            "voice_method": phone.voice_method,
            "status_callback": phone.status_callback,
            "status_callback_method": phone.status_callback_method,
            "voice_fallback_url": phone.voice_fallback_url,
            "voice_fallback_method": phone.voice_fallback_method,
            "sms_fallback_url": phone.sms_fallback_url,
            "sms_fallback_method": phone.sms_fallback_method,
            "address_sid": phone.address_sid,
            "bundle_sid": phone.bundle_sid,
            "identity_sid": phone.identity_sid,
            "trunk_sid": phone.trunk_sid,
            "voice_application_sid": phone.voice_application_sid,
            "sms_application_sid": phone.sms_application_sid,
            "voice_receive_mode": phone.voice_receive_mode,
            "voice_caller_id_lookup": phone.voice_caller_id_lookup,
            "emergency_status": phone.emergency_status,
            "emergency_address_sid": phone.emergency_address_sid,
            "emergency_address_status": phone.emergency_address_status,
            "api_version": phone.api_version,
            "address_requirements": phone.address_requirements,
            "beta": phone.beta,
            "uri": phone.uri,
            "date_created": phone.date_created,
            "date_updated": phone.date_updated,
        }

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def purchase(self, request):
        data = request.data
        phone_number = data.get("phone_number", None)

        if phone_number is not None:
            try:
                payload = {"phone_number": phone_number,}
                client =self.get_trial_client()
                purchased = client.incoming_phone_numbers.create(**payload)
                logger.info("Phone number purchased successfully (%s)", purchased.phone_number,)
                serialize_phone_number = self.to_dict(purchased)

                obj, created = FreeTrailPhoneNumber.objects.update_or_create(
                    provider_phone_sid=serialize_phone_number["sid"],
                    phone_number=serialize_phone_number["phone_number"],
                    defaults={
                        "owner_account_sid": self.MASTER_ACCOUNT_SID,
                        "account_sid": self.FREE_TRAIL_ACCOUNT_SID,
                        "account_auth_token": self.FREE_TRAIL_AUTH_TOKEN,
                        "capabilities": serialize_phone_number["capabilities"],
                        "metadata": serialize_phone_number,
                        "status": PhoneNumberStatus.ACTIVE,

                        "purchased_at": serialize_phone_number["date_created"],
                        "last_synced_at": serialize_phone_number["date_updated"],
                        "is_used": False,
                        "webhook_url": serialize_phone_number["sms_url"] or "",
                    },
                )
                
                return Response(
                    {
                        "success": True,
                        "message": "Trial number purchased successfully.",
                        "data": self.get_serializer(obj).data
                    }, status=status.HTTP_201_CREATED
                )
            except TwilioRestException as e:
                print("e: ", e)
                return Response(
                    {
                        "success": False,
                        "detail": str(e),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {
                    "success": False,
                    "message": "Parchase Number field is empty."
                }, status=status.HTTP_400_BAD_REQUEST
            )
    

    # Sub Account Create in Twilio---
    def serialize_subaccount(self, sub_account):
        return {
            "sid": sub_account.sid,
            "friendly_name": sub_account.friendly_name,
            "status": sub_account.status,
            "owner_account_sid": sub_account.owner_account_sid,
            # "date_created": sub_account.date_created,
            "auth_token": sub_account.auth_token,
        }
    
    @action(detail=False, methods=["post"], url_path="create-free-trail-account")
    @transaction.atomic
    def create_free_trail_account(self, request):
        data = request.data
        account_name = data.get("account_name", None)

        # ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        # AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        # client = Client(ACCOUNT_SID, AUTH_TOKEN)
        # sub_account = client.api.accounts.create(
        #     friendly_name=account_name
        # )
        # serialize_subaccount = self.serialize_subaccount(sub_account)
        return Response(
            {
                "success": True,
                # "data": serialize_subaccount,
            },
            status=status.HTTP_200_OK,
        ) 


    # Release Twilio Number---
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def release(self, request, pk):
        object = self.get_object()
        trial_client = self.get_trial_client()
        trial_client.incoming_phone_numbers(object.provider_phone_sid).delete()

        object.status = PhoneNumberStatus.RELEASED
        object.released_at = timezone.now()
        object.last_synced_at = timezone.now()
        object.save()
        return Response(
            {
                "success": True,
                "message": "Trial number released successfully.",
            },
            status=status.HTTP_200_OK,
        )


    # Sync Twilio Number---
    @action(detail=True, methods=["get"])
    @transaction.atomic
    def sync(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)
        phone  = client.incoming_phone_numbers(object.provider_phone_sid).fetch()
        phone_serializer = self.to_dict(phone)
        return Response(
            {
                "success": True,
                "data": phone_serializer
            }, status=status.HTTP_200_OK
        )

    
    def serializer_tfv(self, record):
        return {
            "sid": record.sid,
            "account_sid": record.account_sid,
            "customer_profile_sid": record.customer_profile_sid,
            "regulated_item_sid": record.regulated_item_sid,
            "trust_product_sid": record.trust_product_sid,
            "business_name": record.business_name,
            "status": record.status,
            "date_created": record.date_created,
            "date_updated": record.date_updated,
            "business_street_address": record.business_street_address,
            "business_street_address2": record.business_street_address2,
            "business_city": record.business_city,
            "business_state_province_region": record.business_state_province_region,
            "business_postal_code": record.business_postal_code,
            "business_country": record.business_country,
            "business_website": record.business_website,
            "business_contact_first_name": record.business_contact_first_name,
            "business_contact_last_name": record.business_contact_last_name,
            "business_contact_email": record.business_contact_email,
            "business_contact_phone": record.business_contact_phone,
            "notification_email": record.notification_email,
            "use_case_categories": record.use_case_categories,
            "use_case_summary": record.use_case_summary,
            "production_message_sample": record.production_message_sample,
            "opt_in_image_urls": record.opt_in_image_urls,
            "opt_in_type": record.opt_in_type,
            "message_volume": record.message_volume,
            "additional_information": record.additional_information,
            "tollfree_phone_number_sid": record.tollfree_phone_number_sid,
            "rejection_reason": record.rejection_reason,
            "error_code": record.error_code,
            "edit_expiration": record.edit_expiration,
            "edit_allowed": record.edit_allowed,
            "rejection_reasons": record.rejection_reasons,
            "resource_links": record.resource_links,
            "url": record.url,
            "external_reference_id": record.external_reference_id,

            # // New response fields for the 2026 update
            "business_registration_number": record.business_registration_number,
            "business_registration_authority": record.business_registration_authority,
            "business_registration_country": record.business_registration_country,
            "doing_business_as": record.doing_business_as,
            "business_type": record.business_type,
            # "opt_in_confirmation_sample": record.opt_in_confirmation_sample,
            "help_message_sample": record.help_message_sample,
            "privacy_policy_url": record.privacy_policy_url,
            # "terms_and_condition_url": record.terms_and_condition_url,
            "age_gated_content": record.age_gated_content,
            "opt_in_keywords": record.opt_in_keywords,
            
            # // New response fields for CV Token update
            "vetting_id": record.vetting_id,       
            "vetting_provider": record.vetting_provider,
            "vetting_id_expiration": record.vetting_id_expiration
        }

    @action(detail=True, methods=["get"], url_path="tfv-fetch")
    def TFVRequestForIncommingNumber(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)
        tfv_sid = request.data.get("tfv_sid")

        if tfv_sid:
            tollfree_verifications = client.messaging.v1.tollfree_verifications(
                tfv_sid
            ).fetch()
            data = self.serializer_tfv(tollfree_verifications)
        else:
            tollfree_verifications = client.messaging.v1.tollfree_verifications.list(
                tollfree_phone_number_sid=object.provider_phone_sid, limit=20
            )
            data = []
            for record in tollfree_verifications:
                data.append(self.serializer_tfv(record))
        return Response(
            {
                "succcess": True,
                "data": data
            }
        )
    
    @TFVRequestForIncommingNumber.mapping.post
    def TFVRequestCreate(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)
        tollfree_verification = client.messaging.v1.tollfree_verifications.create(
            customer_profile_sid="BUaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            business_name="Owl, Inc.",
            business_website="http://www.example.com",
            notification_email="support@example.com",
            use_case_categories=["TWO_FACTOR_AUTHENTICATION", "MARKETING"],
            use_case_summary="This number is used to send out promotional offers and coupons to the customers of Owl, Inc.",
            production_message_sample="lorem ipsum",
            opt_in_image_urls=[
                "https://example.com/images/image1.jpg",
                "https://example.com/images/image2.jpg",
            ],
            opt_in_type="VERBAL",
            message_volume="10",
            additional_information="privacy policy is geo-locked to NAMER region",
            tollfree_phone_number_sid="PNaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            vetting_id="cv|1.0|mno|tfree|b344a16f-b435-4a39-bf91-df9b8e4e0a0d|E5eh-rOPHCr_lrgHDYEZP45FzuJSHS1fkFTmVPD8GQ4",
            vetting_provider="CAMPAIGN_VERIFY",
        )

        print(tollfree_verification.sid)
        return Response(
            {
                "succcess": True,
                "data": "tollfree_verifications"
            }
        )

    @TFVRequestForIncommingNumber.mapping.patch
    def TFVRequestReSubmit(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)

        tfv_sid = request.data.get("tfv_sid")
        print("not tfv_sid: ", not tfv_sid)
        if not tfv_sid:
            raise ValidationError("TFV SID Must be set")
        else:
            tollfree_verifications = client.messages.v1.tollfree_verifications(
                tfv_sid
            )
            # if tollfree_verifications.fetch().status != 
            # tollfree_verifications = client.messaging.v1.tollfree_verifications(
            #     tfv_sid
            # ).update(
            #     edit_reason="Updated the Verbal Consent Script",
            #     # use_case_categories=["TWO_FACTOR_AUTHENTICATION", "MARKETING"],
            #     # use_case_summary="This number is used to send out promotional offers and coupons to the customers of Owl, Inc.",
            #     # production_message_sample="Get 10% off when you save this coupon: https://bit.ly/owlcoupon",
            #     opt_in_image_urls=[
            #         "https://prnt.sc/NFKFNgmoCFOO",
            #         "https://trychesera.com/sms-consent",
            #     ],
            #     opt_in_type="VERBAL",
            #     message_volume="1,000",
            #     privacy_policy_url="https://trychesera.com/privacy",
            #     terms_and_conditions_url="https://trychesera.com/terms"
            # )
            print("tollfree_verifications sid: ", tollfree_verifications.sid)
            data = self.serializer_tfv(tollfree_verifications)
            

            return Response(
                {
                    "succcess": True,
                    "data": data
                }
            )
    
    @action(detail=True, methods=["get"], url_path="sms-consent")
    def sms_consent(self, request, *args, **kwargs):
        context = {
            "organization_logo": None,
            "organization_name": "Chesera LLC",
            "organization_email": "cosmascheseret@gmail.com",
            "organization_website": "https://trychesera.com/",
            "organization_privacy_policy": "https://trychesera.com/",
            "organization_terms_of_service": "https://trychesera.com/",

        }
        return render(request, "sms_consent2.html", context)

    # Update Twilio Number---
    @action(detail=True, methods=["post"], url_path="update-twilio-phone")
    def update_twilio_phone(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)      
        phone = client.incoming_phone_numbers(object.provider_phone_sid).update(
            sms_url="https://api.remyza.com/api/v1/twilio/webhook/",
            sms_method="POST",
        )

        print(phone.sms_url)

        phone_serializer = self.to_dict(phone)
        return Response(
            {
                "success": True,
                "data": phone_serializer
            }, status=status.HTTP_200_OK
        )


    @action(detail=True, methods=["post"], url_path="send-test-sms")
    @transaction.atomic
    def send_test_sms(self, request, pk=None):
        phone_number = self.get_object()

        serializer = SendSMSSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # client = self.get_trial_client()
        client = self.get_client(phone_number)

        try:
            message = client.messages.create(
                from_=phone_number.phone_number,
                to=serializer.validated_data["to"],
                body=serializer.validated_data["body"],
            )
            print("message--------: ", message)
            print("message dict--------: ", message.__dict__)

            return Response(
                {
                    "success": True,
                    "message": "SMS sent successfully.",
                    "data": {
                        "sid": message.sid,
                        "status": message.status,
                        "from": message.from_,
                        "to": message.to,
                        "body": message.body,
                        "date_created": message.date_created,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except TwilioRestException as e:
            return Response(
                {
                    "success": False,
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )




    
    def all_number_synce(self):
        object = self.get_object()
        trial_client = self.get_trial_client()
        numbers = trial_client.incoming_phone_numbers.list(limit=100)
        for number in numbers:
            all_number = (
                {
                    "sid": number.sid,
                    "phone_number": number.phone_number,
                    "friendly_name": number.friendly_name,
                    "account_sid": number.account_sid,
                    "country": number.iso_country,
                    "capabilities": number.capabilities,
                    "voice_url": number.voice_url,
                    "sms_url": number.sms_url,
                    "date_created": number.date_created,
                    "uri": number.uri,
                }
            )
        return all_number

    def get_client(self, object: FreeTrailPhoneNumber):
        return Client(object.account_sid, object.account_auth_token)
        # return Client(object.account_sid, object.account_auth_token)
    
    def get_trial_client(self):
        return Client(self.FREE_TRAIL_ACCOUNT_SID, self.FREE_TRAIL_AUTH_TOKEN)

    def get_master_client(self):
        return Client(self.MASTER_ACCOUNT_SID, self.MASTER_AUTH_TOKEN)

class TwilioWebhookHandler(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def _log_request(self, request):
        raw_body = request.body.decode("utf-8", errors="ignore")
        print("raw: " , raw_body)

        # try:
        #     payload = request.data.dict()
        # except AttributeError:
        #     payload = dict(request.data)

        # TwilioWebhookLog.objects.create(
        #     method=request.method,
        #     path=request.path,
        #     headers=dict(request.headers),
        #     payload=raw_body,
        #     body=raw_body,
        #     ip_address=self.get_client_ip(request),
        # )

    def get(self, request, *args, **kwargs):
        # self._log_request(request)
        return Response(
            {
                "success": True,
                "message": "Twilio Webhook endpoint is working.",
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        self._log_request(request)
        return Response(
            {
                "success": True,
                "message": "Webhook received successfully.",
            },
            status=status.HTTP_200_OK,
        )

