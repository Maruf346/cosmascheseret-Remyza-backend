from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
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
from .serializers import (
    FreeTrailPhoneNumberSerializer, SearchTrialNumberSerializer, SendSMSSerializer, TollFreeVerificationSubmitSerializer, TollFreeVerificationSerializer
)
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

from twilio_app.service.twilio_service import TwilioService
from twilio_app.helper import TFV_to_dict

class FreeTrailPhoneNumberViewSet(OwnReadOnlyModelViewSet):
    serializer_class = FreeTrailPhoneNumberSerializer
    queryset = (FreeTrailPhoneNumber.objects.select_related().order_by("phone_number"))

    FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
    FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")

    MASTER_ACCOUNT_SID = os.getenv("ACCOUNT_SID")
    MASTER_AUTH_TOKEN = os.getenv("AUTH_TOKEN")

    # =============================================
    # =========Only Twilio API=====================
    @action(detail=False, methods=["get"], url_path="search-number")
    def search_number(self, request):
        country = request.query_params.get("country", "US")
        type = request.query_params.get("type", "toll_free")
        area_code = request.query_params.get("area_code", None)
        limit = request.query_params.get("limit", 2)
        search = request.query_params.get("search", None)

        twilio_service = TwilioService()
        if search:
            numbers_list = twilio_service.check_availability(
                phone_type=type,
                contains=search
            )
        else:
            numbers_list = twilio_service.search_numbers(
                phone_type=type,
                country=country,
                area_code=area_code,
                limit=limit
            )
        return Response(
            {
                "success": True,
                "count": len(numbers_list),
                "phone_type": type,
                "results": numbers_list,
            },
            status=status.HTTP_200_OK,
        )

    # Purchase Number from Twilio---
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def purchase(self, request):
        data = request.data
        phone_number = data.get("phone_number", None)

        if phone_number is not None:
            try:
                payload = {"phone_number": phone_number,}

                twilio_service = TwilioService()
                free_trail_number = twilio_service.purchase_free_trail_number(phone_number=phone_number)
                return Response(
                    {
                        "success": True,
                        "message": "Trial number purchased successfully.",
                        "data": self.get_serializer(free_trail_number).data
                    }, status=status.HTTP_201_CREATED
                )
            except TwilioRestException as e:
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
    
    @action(detail=False, methods=["post"], url_path="add-trail-number")
    @transaction.atomic
    def add_toll_free_number(self, request):
        data = request.data
        phone_number = data.get("phone_number", None)
        return Response(
            {
                "success": True,
                "message": "Trial number add successfully.",
                # "data": self.get_serializer(free_trail_number).data
            }, status=status.HTTP_201_CREATED
        ) 


    # Release Twilio Number---
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def release(self, request, pk):
        object = self.get_object()

        twilio_service = TwilioService()
        twilio_service.release_number(object)

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
        twilio_service = TwilioService()
        phone_serializer = twilio_service.sync(object)
        return Response(
            {
                "success": True,
                "data": phone_serializer
            }, status=status.HTTP_200_OK
        )

    # =========Only Twilio API=====================
    # =============================================

    # =============================================
    # =========Only Twilio TFV API=================
    @action(detail=True, methods=["get"], url_path="tfv-sync")
    @transaction.atomic
    def TFVRequestForIncommingNumberSync(self, request, pk):
        object = self.get_object()
        tfv_sid = request.data.get("tfv_sid", None)

        twilio_service = TwilioService()
        tfv_verification = twilio_service.sync_tfv_verification(object)
        return Response(
            {
                "succcess": True,
                "data": tfv_verification
            }
        )

    @action(detail=True, methods=["get"], url_path="tfv")
    def TFVRequestForIncommingNumber(self, request, pk):
        object = self.get_object()
        local_tfv = getattr(object, "tfv_verification", None)
        if local_tfv:
            return Response(
                {
                    "success": True,
                    "data": TollFreeVerificationSerializer(local_tfv).data
                }
            )
        return Response(
            {
                "success": False,
                "data": "No TFV verification submitted yet."
            }
        )
    
    @action(detail=True, methods=["post"], url_path="tfv/submit")
    def TFVRequestSubmit(self, request, pk):
        try:
            object = self.get_object()
            client = self.get_client(object)

            twilio_service = TwilioService()
            selected, data = twilio_service.get_latest_ftv(object, client)
            if selected:
                return Response(
                    {
                        "succcess": False,
                        "message": f"Already have {selected.status} TFV Submitted."
                    }
                )

            serializer = TollFreeVerificationSubmitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payload = serializer.get_payload(object)
            twilio_service.submit_tfv_verification(object, payload, client)
            return Response(
                {
                    "succcess": True,
                    "data": payload
                }, status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {
                    "succcess": False,
                    "data": str(e)
                }, status=status.HTTP_200_OK
            )

    @action(detail=True, methods=["patch"], url_path="tfv/re-submit")
    def TFVRequestReSubmit(self, request, pk):
        object = self.get_object()
        client = self.get_client(object)
        tfv_verification = getattr(object, "tfv_verification", None)

        tfv_sid = request.data.get("tfv_sid")
        if not tfv_sid:
            raise ValidationError("TFV SID Must be set")
        elif not tfv_verification or tfv_sid != tfv_verification.verification_sid:
            raise ValidationError("Worng SID")
        else:
            # twilio_service = TwilioService()
            # selected, data = twilio_service.get_latest_ftv(object, client)
            tollfree_verifications = client.messaging.v1.tollfree_verifications(
                tfv_sid
            ).fetch()
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
            return Response(
                {
                    "succcess": True,
                    "data": TFV_to_dict(tollfree_verifications)
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
    
    # =========Only Twilio TFV API=================
    # =============================================

    # =============================================
    # ======Only Twilio Sub-Account API============
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
    
    # ======Only Twilio Sub-Account API============
    # =============================================
    
    
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

BusinessTypeViewSet = extend_schema_view(
    list=extend_schema(
        tags=["Reference Data"],
        summary="List business types",
        description="Returns active business type options used during business profile setup.",
        responses={200: BusinessTypeSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Reference Data"],
        summary="Get business type",
        description="Returns one business type by ID.",
        responses={200: BusinessTypeSerializer, 404: OpenApiResponse(description="Business type not found.")},
    ),
    create=extend_schema(
        tags=["Reference Data"],
        summary="Create business type",
        description="Creates a business type option. Admin access is required.",
        request=BusinessTypeSerializer,
        responses={201: BusinessTypeSerializer, 400: OpenApiResponse(description="Invalid business type data.")},
    ),
    update=extend_schema(
        tags=["Reference Data"],
        summary="Update business type",
        description="Updates a business type option. Admin access is required.",
        request=BusinessTypeSerializer,
        responses={200: BusinessTypeSerializer, 400: OpenApiResponse(description="Invalid business type data.")},
    ),
    partial_update=extend_schema(
        tags=["Reference Data"],
        summary="Partially update business type",
        description="Partially updates a business type option. Admin access is required.",
        request=BusinessTypeSerializer,
        responses={200: BusinessTypeSerializer, 400: OpenApiResponse(description="Invalid business type data.")},
    ),
    destroy=extend_schema(
        tags=["Reference Data"],
        summary="Delete business type",
        description="Deletes a business type option. Admin access is required.",
        responses={200: OpenApiResponse(description="Business type deleted successfully.")},
    ),
)(BusinessTypeViewSet)

IndustryViewSet = extend_schema_view(
    list=extend_schema(
        tags=["Reference Data"],
        summary="List industries",
        description="Returns active industry options used during business profile setup.",
        responses={200: IndustrySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Reference Data"],
        summary="Get industry",
        description="Returns one industry by ID.",
        responses={200: IndustrySerializer, 404: OpenApiResponse(description="Industry not found.")},
    ),
    create=extend_schema(
        tags=["Reference Data"],
        summary="Create industry",
        description="Creates an industry option. Admin access is required.",
        request=IndustrySerializer,
        responses={201: IndustrySerializer, 400: OpenApiResponse(description="Invalid industry data.")},
    ),
    update=extend_schema(
        tags=["Reference Data"],
        summary="Update industry",
        description="Updates an industry option. Admin access is required.",
        request=IndustrySerializer,
        responses={200: IndustrySerializer, 400: OpenApiResponse(description="Invalid industry data.")},
    ),
    partial_update=extend_schema(
        tags=["Reference Data"],
        summary="Partially update industry",
        description="Partially updates an industry option. Admin access is required.",
        request=IndustrySerializer,
        responses={200: IndustrySerializer, 400: OpenApiResponse(description="Invalid industry data.")},
    ),
    destroy=extend_schema(
        tags=["Reference Data"],
        summary="Delete industry",
        description="Deletes an industry option. Admin access is required.",
        responses={200: OpenApiResponse(description="Industry deleted successfully.")},
    ),
)(IndustryViewSet)
