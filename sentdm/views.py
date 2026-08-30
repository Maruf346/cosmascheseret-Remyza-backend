from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .client import SentDMClient, SentDMClientError
from .models import SentDMProfile
from .serializers import *
from .services import *


def sentdm_error_response(exc):
    if isinstance(exc, ImproperlyConfigured):
        return Response(
            {"success": False, "message": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, SentDMClientError):
        return Response(
            {
                "success": False,
                "message": str(exc),
                "request_id": exc.request_id,
                "data": exc.response_data,
            },
            status=exc.status_code or status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"success": False, "message": str(exc)},
        status=status.HTTP_400_BAD_REQUEST,
    )


def get_requested_or_current_profile(user, profile_id=None):
    if profile_id:
        profile = SentDMProfile.objects.filter(profile_id=profile_id).first()
        if not profile:
            raise ValidationError({"profile_id": "Sent.dm profile not found."})
        return profile

    if hasattr(user, "sentdm_profile"):
        return user.sentdm_profile

    return None


def get_current_profile_or_404(user):
    profile = SentDMProfile.objects.filter(user=user).first()
    if not profile and hasattr(user, "organization"):
        profile = SentDMProfile.objects.filter(organization=user.organization).first()
    if not profile:
        raise NotFound("Sent.dm profile not found for current user.")
    return profile


class SentDMAccountCheckAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SentDMAccountCheckSerializer)
    def get(self, request):
        try:
            data = SentDMClient().get_account()
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMProfileListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SentDMAccountCheckSerializer)
    def get(self, request):
        try:
            data = SentDMClient().list_profiles()
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMProfileCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMProfileCreateSerializer

    @extend_schema(request=SentDMProfileCreateSerializer, responses=SentDMProfileSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile, response = create_profile_for_user(request.user)
            return Response(
                {
                    "success": True,
                    "message": "Sent.dm Sender Profile request accepted.",
                    "sandbox": settings.SENTDM_SANDBOX_MODE,
                    "data": {
                        "profile": SentDMProfileSerializer(profile).data if profile else None,
                        "sentdm_response": response,
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMCurrentProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SentDMProfileSerializer)
    def get(self, request):
        return Response(
            {"success": True, "data": SentDMProfileSerializer(get_current_profile_or_404(request.user)).data},
            status=status.HTTP_200_OK,
        )


class SentDMProfileCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMProfileCompleteSerializer

    @extend_schema(request=SentDMProfileCompleteSerializer, responses=SentDMAccountCheckSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile_id = serializer.validated_data.get("profile_id")
        profile = SentDMProfile.objects.filter(profile_id=profile_id).first() if profile_id else get_current_profile_or_404(request.user)
        if not profile:
            raise NotFound("Sent.dm profile not found.")

        try:
            response = complete_profile(profile, request)
            return Response(
                {
                    "success": True,
                    "message": "Sent.dm Sender Profile completion request accepted.",
                    "sandbox": settings.SENTDM_SANDBOX_MODE,
                    "data": response,
                },
                status=status.HTTP_200_OK,
            )
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMSendSandboxMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMSendSandboxMessageSerializer

    @extend_schema(request=SentDMSendSandboxMessageSerializer, responses=SentDMMessageSerializer)
    def post(self, request):
        if not settings.SENTDM_SANDBOX_MODE:
            raise ValidationError({"sandbox": "SENTDM_SANDBOX_MODE must be True for this endpoint."})

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_requested_or_current_profile(request.user, serializer.validated_data.get("profile_id"))

        try:
            message, response = send_sandbox_message(
                user=request.user,
                to=serializer.validated_data["to"],
                text=serializer.validated_data["text"],
                profile=profile,
                channel=serializer.validated_data["channel"],
            )
            return Response(
                {
                    "success": True,
                    "message": "Sent.dm message request accepted.",
                    "sandbox": settings.SENTDM_SANDBOX_MODE,
                    "data": {
                        "message": SentDMMessageSerializer(message).data,
                        "sentdm_response": response,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMSendMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMSendSandboxMessageSerializer

    @extend_schema(request=SentDMSendSandboxMessageSerializer, responses=SentDMMessageSerializer)
    def post(self, request):
        if settings.SENTDM_SANDBOX_MODE:
            raise ValidationError({"sandbox": "Disable SENTDM_SANDBOX_MODE before using the live Sent.dm send endpoint."})

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_requested_or_current_profile(request.user, serializer.validated_data.get("profile_id"))
        if not profile:
            raise ValidationError({"profile": "A live Sent.dm Sender Profile is required before sending."})

        try:
            message, response = send_live_message(
                user=request.user,
                to=serializer.validated_data["to"],
                text=serializer.validated_data["text"],
                profile=profile,
                channel=serializer.validated_data["channel"],
            )
            return Response(
                {
                    "success": True,
                    "message": "Sent.dm live message request accepted.",
                    "sandbox": settings.SENTDM_SANDBOX_MODE,
                    "data": {
                        "message": SentDMMessageSerializer(message).data,
                        "sentdm_response": response,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMInboundWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses=SentDMWebhookEventSerializer)
    def post(self, request):
        event, accepted = create_webhook_event(request, allow_unverified_in_debug=True)
        if not accepted:
            return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(
            {
                "success": True,
                "message": "Sent.dm inbound webhook received.",
                "data": SentDMWebhookEventSerializer(event).data,
            },
            status=status.HTTP_200_OK,
        )


class SentDMProfileReadyWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses=SentDMWebhookEventSerializer)
    def post(self, request):
        event, accepted = create_webhook_event(request, allow_unverified_in_debug=True)
        if not accepted:
            return Response({"success": False, "message": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

        payload = event.payload
        profile_id = payload.get("profileId") or payload.get("profile_id")
        status_value = payload.get("status")
        if profile_id and status_value:
            SentDMProfile.objects.filter(profile_id=profile_id).update(
                status=normalize_profile_status(status_value),
                raw_response=payload,
            )

        return Response(
            {
                "success": True,
                "message": "Sent.dm profile-ready webhook received.",
                "data": SentDMWebhookEventSerializer(event).data,
            },
            status=status.HTTP_200_OK,
        )