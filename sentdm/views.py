from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .client import SentDMClient, SentDMClientError
from .models import SentDMProfile
from .serializers import (
    SentDMAccountCheckSerializer,
    SentDMMessageSerializer,
    SentDMProfileCompleteSerializer,
    SentDMProfileCreateSerializer,
    SentDMProfileSerializer,
    SentDMWebhookEventSerializer,
    SentDMSendSandboxMessageSerializer,
)
from .services import (
    complete_profile,
    create_profile_for_user,
    create_webhook_event,
    normalize_profile_status,
    send_live_message,
    send_sandbox_message,
)


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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Check Sent.dm account",
        description="Calls Sent.dm `/me` with the configured API key. Use this to confirm the key is valid and inspect account/channel/profile readiness.",
        responses={
            200: SentDMAccountCheckSerializer,
            500: OpenApiResponse(description="Sent.dm API key or base URL is not configured."),
            400: OpenApiResponse(description="Sent.dm returned an error."),
        },
    )
    def get(self, request):
        try:
            data = SentDMClient().get_account()
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMProfileListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Sent.dm"],
        summary="List Sent.dm Sender Profiles",
        description="Lists Sender Profiles available to the configured Sent.dm API key. In sandbox mode this can be used to validate the endpoint shape.",
        responses={200: SentDMAccountCheckSerializer, 400: OpenApiResponse(description="Sent.dm returned an error.")},
    )
    def get(self, request):
        try:
            data = SentDMClient().list_profiles()
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        except (ImproperlyConfigured, SentDMClientError) as exc:
            return sentdm_error_response(exc)


class SentDMProfileCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMProfileCreateSerializer

    @extend_schema(
        tags=["Sent.dm"],
        summary="Create Sender Profile",
        description="Creates a Sent.dm Sender Profile for the authenticated user's organization. When `SENTDM_SANDBOX_MODE=True`, the request is sent with `sandbox: true` and no real profile is provisioned.",
        request=SentDMProfileCreateSerializer,
        responses={
            201: SentDMProfileSerializer,
            400: OpenApiResponse(description="Invalid payload or Sent.dm rejected the request."),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile, response = create_profile_for_user(request.user, serializer.validated_data)
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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Get current Sender Profile",
        description="Returns the Sent.dm Sender Profile stored for the authenticated user or their organization.",
        responses={200: SentDMProfileSerializer, 404: OpenApiResponse(description="No Sender Profile exists for the current user.")},
    )
    def get(self, request):
        return Response(
            {"success": True, "data": SentDMProfileSerializer(get_current_profile_or_404(request.user)).data},
            status=status.HTTP_200_OK,
        )


class SentDMProfileCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SentDMProfileCompleteSerializer

    @extend_schema(
        tags=["Sent.dm"],
        summary="Complete Sender Profile onboarding",
        description="Requests Sent.dm to complete/onboard a Sender Profile and registers Chesera's profile-ready webhook URL. Sandbox mode simulates the completion flow.",
        request=SentDMProfileCompleteSerializer,
        responses={
            200: SentDMAccountCheckSerializer,
            400: OpenApiResponse(description="Profile is missing or Sent.dm rejected the completion request."),
            404: OpenApiResponse(description="Sender Profile not found."),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile_id = serializer.validated_data.get("profile_id")
        profile = SentDMProfile.objects.filter(profile_id=profile_id).first() if profile_id else get_current_profile_or_404(request.user)
        if not profile:
            raise NotFound(
                "Sent.dm profile not found. Use the returned data.profile.profile_id "
                "from /api/v1/sentdm/profiles/create/, not the local database id."
            )

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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Send sandbox message",
        description="Sends a sandbox Sent.dm message request for integration testing. This endpoint is blocked unless `SENTDM_SANDBOX_MODE=True`.",
        request=SentDMSendSandboxMessageSerializer,
        responses={
            202: SentDMMessageSerializer,
            400: OpenApiResponse(description="Sandbox mode is disabled, payload is invalid, or Sent.dm rejected the request."),
        },
    )
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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Send live message",
        description="Prepared production send endpoint. It is not currently routed in `sentdm/urls.py`; enable only after live Sent.dm credentials, approved Sender Profiles, webhook secret, and lead/conversation routing are ready.",
        request=SentDMSendSandboxMessageSerializer,
        responses={
            202: SentDMMessageSerializer,
            400: OpenApiResponse(description="Sandbox mode is enabled, profile is missing, payload is invalid, or Sent.dm rejected the request."),
        },
    )
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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Receive inbound message webhook",
        description="Receives Sent.dm inbound message webhooks. The handler verifies the webhook signature when a secret is configured, stores the raw event, and returns quickly for async processing.",
        request=None,
        responses={
            200: SentDMWebhookEventSerializer,
            401: OpenApiResponse(description="Invalid webhook signature."),
        },
    )
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

    @extend_schema(
        tags=["Sent.dm"],
        summary="Receive Sender Profile status webhook",
        description="Receives Sent.dm Sender Profile status updates and stores the raw event. When a profile ID and status are present, Chesera updates the local Sender Profile status.",
        request=None,
        responses={
            200: SentDMWebhookEventSerializer,
            401: OpenApiResponse(description="Invalid webhook signature."),
        },
    )
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