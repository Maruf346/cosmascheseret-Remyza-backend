from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework import response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.serializers import TokenRefreshSerializer, TokenVerifySerializer
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from .choices import OTPPurpose, UserType
from .models import OTPVerification, User
from sentdm.models import SentDMProfile

from business.serializers import OrganizationSerializer, ProviderAccountSerializer
from business.models import PhoneNumber
from .serializers import (
    AdminLoginSerializer,
    ClientSignupSerializer,
    ClientSendOTPSerializer,
    ClientVerifyOTPSerializer,
    CurrentUserSerializer,
    CurrentUserCheseraNumberSerializer,
)
from django.db import transaction
from notifications.services import NotificationTemplates, safe_notify



class ClientSignupAPIView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ClientSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"]
        user, created = User.objects.get_or_create(
            phone_number=phone,
            defaults={
                "user_type": UserType.CLIENT,
                "is_phone_verified": False,
            },
        )
        for field in ("full_name", "email", "city", "country", "country_code"):
            setattr(user, field, serializer.validated_data.get(field, ""))
        user.user_type = UserType.CLIENT
        user.save(update_fields=["full_name", "email", "city", "country", "country_code", "user_type", "updated_at"])
        OTPVerification.objects.create_otp(
            user=user,
            phone_number=phone,
            purpose=OTPPurpose.REGISTER,
        )

        if created:
            transaction.on_commit(lambda: safe_notify(NotificationTemplates.welcome_user, user))
            transaction.on_commit(lambda: safe_notify(NotificationTemplates.new_user_registered, user))

        return Response(
            {
                "success": True,
                "message": "Signup OTP sent successfully.",
                "data": {
                    "phone_number": user.phone_number,
                    "is_new_user": created,
                    "user": CurrentUserSerializer(user, context={"request": request}).data,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

class ClientSendOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ClientSendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"].strip()
        user, created = User.objects.get_or_create(phone_number=phone)
        OTPVerification.objects.create_otp(
            user=user,
            phone_number=phone,
            purpose=OTPPurpose.LOGIN,
        )

        # TODO: Send OTP via Twilio

        return Response(
            {
                "success": True,
                "message": "OTP sent successfully.",
                "data": {
                    "phone_number": user.phone_number,
                    "is_new_user": created
                }
            },
            status=status.HTTP_200_OK,
        )

class ClientVerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ClientVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "data": {
                    "access": result["access"],
                    "refresh": result["refresh"],
                    "business_profile_exists": True if hasattr(result["user"], "organization") else False,
                    "user": {
                        "id": result["user"].id,
                        "phone_number": result["user"].phone_number,
                        "full_name": result["user"].full_name,
                        "email": result["user"].email,
                        "city": result["user"].city,
                        "country": result["user"].country,
                        "country_code": result["user"].country_code,
                        "user_type": result["user"].user_type,
                        "is_phone_verified": result["user"].is_phone_verified,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )

class AdminLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "data": {
                    "access": serializer.validated_data["access"],
                    "refresh": serializer.validated_data["refresh"],
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "full_name": user.full_name,
                        "user_type": user.user_type,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )

class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "success": True,
                "message": "Token refreshed successfully.",
                "data": serializer.validated_data,
            },
            status=status.HTTP_200_OK,
        )

class CustomTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "success": True,
                "message": "Token is valid.",
            },
            status=status.HTTP_200_OK,
        )



from subscription.services.purchase import SubscriptionValidationService
from subscription.serializers import UserSubscriptionSerializer
from core.models import FreeTrailPhoneNumber, UserFreeTrailNumber, PhoneNumberStatus
from django.db.models import Min
from core.model_serializer import UserFreeTrailNumberSerializer

class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_user(self, request):
        id = request.user.pk
        user = (
            User.objects
            .select_related("organization")
            .get(pk=id)
        )
        return user

    def get(self, request):
        user = self.get_user(request)
        serializer = CurrentUserSerializer(user, context={"request": request})

        active_subscription = SubscriptionValidationService.get_current_subscription(user)

        free_trial = SubscriptionValidationService.get_free_trail_subscription(user)
        free_trail_claimed = SubscriptionValidationService.has_free_trail_claimed(user)
        
        response = {
            "user": serializer.data,
            "has_active_subscription": True if active_subscription else False,

            "free_trail_claimed": free_trail_claimed,
            "free_trial_session": free_trial.status if free_trial else None,
        }

        if active_subscription:
            response["plan_type"] = active_subscription.plan_type,
            response["expires_at"] = active_subscription.expiry_date,
            response["active_subscription"] = UserSubscriptionSerializer(active_subscription).data

        if active_subscription and active_subscription.is_free_trial:
            user_free_trial_number = UserFreeTrailNumber.objects.filter(user=user).first()
            if user_free_trial_number:
                response["free_trial_number"] = UserFreeTrailNumberSerializer(user_free_trial_number).data

        your_business_number = None
        if hasattr(user, "organization") and user.organization.phone_numbers.exists():
            your_business_number = user.organization.phone_numbers.first()


        return Response(
            {
                "success": True,
                "message": "User data retrieved successfully.",
                "data": response
            }, status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def delete(self, request):
        user = self.get_user(request)
        user.delete()
        return Response(
            {
                "success": True,
                "message": "User account deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def patch(self, request):
        user = self.get_user(request)
        serializer = CurrentUserSerializer(user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "success": True,
                "message": "User data updated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

class ClaimFreeTrailNumber(APIView):
    permission_classes = [IsAuthenticated]

    def get_next_free_trial_number(self):
        queryset = FreeTrailPhoneNumber.objects.select_for_update(skip_locked=True).filter(
            is_used=False,
            status=PhoneNumberStatus.ACTIVE,
        )
        

        number = queryset.first()
        if number:
            return number
        else:
            queryset = FreeTrailPhoneNumber.objects.select_for_update(skip_locked=True).filter(
                is_used=True,
                status=PhoneNumberStatus.ACTIVE,
            )
            if not queryset.exists():
                return None

            min_usage = queryset.aggregate(
                min_usage=Min("usages_count")
            )["min_usage"]
            return queryset.filter(
                usages_count=min_usage
            ).order_by("created_at").first()

    def update_after_number_assign(self, selected_number):
        selected_number.is_used = True
        selected_number.usages_count += 1
        selected_number.save(
            update_fields=["is_used", "usages_count",]
        )
        return selected_number

    def get(self, request, *args, **kwargs):
        if UserFreeTrailNumber.objects.filter(user=self.request.user).exists():
            return Response(
                {
                    "success": False,
                    "message": "Free Trail number already assign."
                }, status=status.HTTP_400_BAD_REQUEST
            )

        selected_number = self.get_next_free_trial_number()
        if not selected_number:
            return Response(
                {
                    "success": False,
                    "message": "No free trial number available."
                }, status=status.HTTP_400_BAD_REQUEST
            )

        subscription = SubscriptionValidationService.get_active_free_trail_subscription(self.request.user)
        if not subscription:
            return Response(
                {
                    "success": False,
                    "message": "No active free trial subscription found."
                }, status=status.HTTP_400_BAD_REQUEST,
            )

        user_trail_number = UserFreeTrailNumber.objects.create(
            user=self.request.user,
            free_trail=selected_number,
            trail_number=selected_number.phone_number,
            end_at = subscription.expires_at
        )
        self.update_after_number_assign(selected_number)


        return Response(
            {
                "success": True,
                "message": "",
                "data": UserFreeTrailNumberSerializer(user_trail_number).data
            }
        )


class CurrentUserCheseraNumberAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_profile(self, user):
        if hasattr(user, "organization"):
            profile = SentDMProfile.objects.filter(organization=user.organization).first()
            if profile:
                return profile
        return SentDMProfile.objects.filter(user=user).first()

    def get_number_assignment_status(self, profile):
        if profile and profile.phone_number:
            return "assigned"
        if profile and profile.status == "failed":
            return "needs_attention"
        return "pending"

    def get_number_assignment_message(self, status_value):
        if status_value == "assigned":
            return "Messaging number assigned."
        if status_value == "needs_attention":
            return "Messaging activation needs attention. Number assignment could not be completed automatically."
        return "Messaging activation is in progress. Number assignment may take additional time if local inventory is unavailable."

    @extend_schema(
        tags=["User Chesera Number"],
        summary="Get user's Chesera number",
        description="Returns the authenticated user's dedicated Chesera SMS/RCS number assigned through Sent.dm. Free or pending users receive `assigned=false` with the current activation message.",
        responses={200: CurrentUserCheseraNumberSerializer},
    )
    def get(self, request):
        profile = self.get_profile(request.user)
        number_assignment_status = self.get_number_assignment_status(profile)
        data = {
            "assigned": bool(profile and profile.phone_number),
            "phone_number": profile.phone_number if profile and profile.phone_number else None,
            "status": number_assignment_status,
            "number_assignment_status": number_assignment_status,
            "message": self.get_number_assignment_message(number_assignment_status),
            "provider": "sentdm",
            "profile_id": profile.profile_id if profile else None,
            "profile_status": profile.status if profile else None,
            "sms_rcs_active": bool(profile and profile.phone_number and profile.status in ("approved", "active")),
        }
        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)

class CurrentUserPlanAndProgressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress = {
            "total_steps": 6,
            "completed_steps": 0,
            "percentage": 0,
            "steps": [],
        }
        self.response = {}
        self.organization = None
        self.sentdm_profile = None
        self.sentdm_campaign = None
        self.compliance_ready = False

    def add_progress(self, title, completed, description="", key="", status_value=""):
        weight = int(100 / self.progress["total_steps"])
        if completed:
            self.progress["completed_steps"] += 1

        step = {
            "title": title,
            "completed": completed,
            "percentage": weight,
            "description": description,
        }
        if key:
            step["key"] = key
        if status_value:
            step["status"] = status_value
        self.progress["steps"].append(step)

    def get_active_subscription(self, user):
        return SubscriptionValidationService.get_paid_active_subscription(user)

    def process_subscription(self, user):
        subscription = self.get_active_subscription(user)
        self.response["has_active_subscription"] = subscription is not None
        self.response["plan_type"] = subscription.plan_type if subscription else None
        self.response["expires_at"] = subscription.expiry_date if subscription else None
        self.response["active_subscription"] = UserSubscriptionSerializer(subscription).data if subscription else None
        self.add_progress(
            "Subscription Active",
            subscription is not None,
            "Paid messaging unlocks after an active Apple/Google subscription record exists.",
            key="subscription",
            status_value="active" if subscription else "inactive",
        )
        return subscription

    def process_organization(self, user):
        organization = getattr(user, "organization", None)
        self.organization = organization
        self.response["organization"] = OrganizationSerializer(organization).data if organization else None
        self.add_progress(
            "Business Profile Created",
            organization is not None,
            "Business profile is required before Sent.dm Sender Profile setup.",
            key="business_profile",
            status_value="complete" if organization else "missing",
        )
        return organization

    def process_compliance(self):
        if not self.organization:
            self.response["sentdm_compliance"] = None
            self.add_progress(
                "Compliance Details Added",
                False,
                "Complete the business profile before adding Sent.dm compliance details.",
                key="sentdm_compliance",
                status_value="missing",
            )
            return None

        from sentdm.services import get_sentdm_compliance_readiness

        readiness = get_sentdm_compliance_readiness(self.request.user)
        self.response["sentdm_compliance"] = readiness
        self.compliance_ready = not any(
            field != "sentdm_profile" for field in readiness.get("missing_fields", [])
        )
        self.add_progress(
            "Compliance Details Added",
            self.compliance_ready,
            "Legal business details, opt-in flow, sample messages, autoresponses, and policy links are required for 10DLC.",
            key="sentdm_compliance",
            status_value="complete" if self.compliance_ready else "missing",
        )
        return readiness

    def process_sentdm_profile(self):
        profile = None
        if self.organization:
            profile = getattr(self.organization, "sentdm_profile", None)
        if not profile:
            profile = getattr(self.request.user, "sentdm_profile", None)

        self.sentdm_profile = profile
        self.response["sentdm_profile"] = {
            "id": profile.id,
            "profile_id": profile.profile_id,
            "name": profile.name,
            "status": profile.status,
            "phone_number": profile.phone_number,
            "whatsapp_phone_number": profile.whatsapp_phone_number,
            "whatsapp_connection_source": getattr(profile, "whatsapp_connection_source", "none"),
            "whatsapp_connection_status": getattr(profile, "whatsapp_connection_status", "not_connected"),
            "whatsapp_connection_error": getattr(profile, "whatsapp_connection_error", ""),
            "is_agent_whatsapp_active": getattr(profile, "is_agent_whatsapp_active", False),
            "sandbox": profile.sandbox,
        } if profile else None
        self.add_progress(
            "Sent.dm Sender Profile Created",
            profile is not None,
            "Sender Profile is created after paid subscription and complete business compliance details.",
            key="sentdm_profile",
            status_value=profile.status if profile else "missing",
        )
        return profile

    def get_number_assignment_status(self):
        profile = self.sentdm_profile
        campaign = self.sentdm_campaign
        if profile and profile.phone_number:
            return "assigned"
        if (profile and profile.status == "failed") or (campaign and campaign.status == "FAILED"):
            return "needs_attention"
        return "pending"

    def get_number_assignment_message(self, status_value):
        if status_value == "assigned":
            return "Messaging number assigned."
        if status_value == "needs_attention":
            return "Messaging activation needs attention. Number assignment could not be completed automatically."
        return "Messaging activation is in progress. Number assignment may take additional time if local inventory is unavailable."

    def process_sentdm_number(self):
        phone_number = self.sentdm_profile.phone_number if self.sentdm_profile else ""
        number_assigned = bool(phone_number)
        number_assignment_status = self.get_number_assignment_status()
        number_assignment_message = self.get_number_assignment_message(number_assignment_status)
        self.response["number_assignment_status"] = number_assignment_status
        self.response["sentdm_number"] = {
            "assigned": number_assigned,
            "phone_number": phone_number or None,
            "status": number_assignment_status,
            "number_assignment_status": number_assignment_status,
            "message": number_assignment_message,
        }
        self.add_progress(
            "Sent.dm Number Assigned",
            number_assigned,
            "A dedicated SMS/RCS number is assigned by Sent.dm after Sender Profile processing.",
            key="sentdm_number",
            status_value=number_assignment_status,
        )
        return number_assigned

    def process_sentdm_campaign(self):
        campaign = None
        if self.sentdm_profile:
            campaign = self.sentdm_profile.campaigns.order_by("-created_at").first()

        self.sentdm_campaign = campaign
        self.response["sentdm_campaign"] = {
            "id": campaign.id,
            "campaign_id": campaign.campaign_id,
            "name": campaign.name,
            "status": campaign.status,
            "submitted_to_tcr": campaign.submitted_to_tcr,
            "sandbox": campaign.sandbox,
        } if campaign else None
        self.add_progress(
            "10DLC Campaign Submitted",
            campaign is not None,
            "Campaign submission uses the business compliance details and usually activates within 1-3 business days after real provider approval.",
            key="sentdm_campaign",
            status_value=campaign.status if campaign else "missing",
        )
        return campaign

    def get_whatsapp_status(self):
        profile = self.sentdm_profile
        if not profile:
            return {
                "status": "not_connected",
                "source": "none",
                "active": False,
                "phone_number": None,
                "error": "",
                "message": "WhatsApp is optional and can be connected after the Sender Profile is created.",
            }

        source = getattr(profile, "whatsapp_connection_source", "none") or "none"
        status_value = getattr(profile, "whatsapp_connection_status", "not_connected") or "not_connected"
        active = getattr(profile, "is_agent_whatsapp_active", False)
        if active:
            message = "WhatsApp is active for this agent."
        elif status_value == "failed":
            message = "WhatsApp connection failed. Please check the WABA ID, phone number ID, access token, and Meta permissions."
        elif status_value == "pending":
            message = "WhatsApp connection is pending Sent.dm/Meta acceptance."
        elif source == "inherited":
            message = "WhatsApp is optional and not connected for this agent. SMS/RCS can continue normally."
        else:
            message = "WhatsApp is optional and not connected. SMS/RCS can continue normally."

        return {
            "status": status_value,
            "source": source,
            "active": active,
            "phone_number": profile.whatsapp_phone_number if active else None,
            "error": getattr(profile, "whatsapp_connection_error", ""),
            "message": message,
        }

    def process_activation_status(self, subscription):
        profile = self.sentdm_profile
        campaign = self.sentdm_campaign
        number_assigned = bool(profile and profile.phone_number)
        number_assignment_status = self.response.get("number_assignment_status") or self.get_number_assignment_status()
        campaign_status = campaign.status if campaign else ""
        profile_status = profile.status if profile else ""

        if not subscription:
            status_value = "subscription_required"
            message = "Messaging activates after a paid subscription is active."
        elif not self.organization:
            status_value = "business_profile_required"
            message = "Complete the business profile before messaging activation can start."
        elif not self.compliance_ready:
            status_value = "compliance_required"
            message = "Complete the Sent.dm compliance details before messaging activation can start."
        elif not profile:
            status_value = "sender_profile_required"
            message = "Create the Sent.dm Sender Profile to start messaging activation."
        elif profile_status == "failed" or campaign_status == "FAILED":
            status_value = "needs_attention"
            message = "Messaging activation needs attention."
        elif number_assigned and campaign and campaign_status == "ACTIVE":
            status_value = "active"
            message = "Messaging active."
        elif number_assigned and campaign:
            status_value = "activation_in_progress"
            message = "Messaging activation in progress, usually 1-3 business days."
        elif number_assigned:
            status_value = "campaign_required"
            message = "Messaging number is assigned. Submit the 10DLC campaign to continue activation."
        else:
            status_value = "activation_in_progress"
            message = "Messaging activation in progress, usually 1-3 business days."

        self.response["whatsapp"] = self.get_whatsapp_status()
        self.response["messaging_activation"] = {
            "status": status_value,
            "message": message,
            "sms_rcs": {
                "number_assigned": number_assigned,
                "number_assignment_status": number_assignment_status,
                "phone_number": profile.phone_number if profile and profile.phone_number else None,
                "profile_status": profile_status or None,
                "campaign_status": campaign_status or None,
                "active": status_value == "active",
            },
            "whatsapp": self.response["whatsapp"],
        }

    def finalize_progress(self):
        self.progress["percentage"] = int(
            self.progress["completed_steps"] * 100 / self.progress["total_steps"]
        )
        self.response["progress"] = self.progress

    def get(self, request):
        self.request = request
        user = request.user

        subscription = self.process_subscription(user)
        self.process_organization(user)
        self.process_compliance()
        self.process_sentdm_profile()
        self.process_sentdm_campaign()
        self.process_sentdm_number()
        self.process_activation_status(subscription)
        self.finalize_progress()

        return Response({
            "success": True,
            "message": "User plan and Sent.dm setup progress retrieved successfully.",
            "data": self.response,
        })
ClientSignupAPIView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - User"],
        summary="Signup and send OTP",
        description="Creates or updates an unverified client user with full name, email, phone number, city, country, and optional country code, then sends a registration OTP. JWT tokens are returned after OTP verification.",
        request=ClientSignupSerializer,
        responses={
            201: OpenApiResponse(description="New user created and signup OTP session started."),
            200: OpenApiResponse(description="Existing unverified user updated and signup OTP resent."),
            400: OpenApiResponse(description="Invalid signup payload or verified user already exists."),
        },
    ),
)(ClientSignupAPIView)
ClientSendOTPAPIView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - User"],
        summary="Send login OTP",
        description="Creates or finds a client user by phone number and starts an OTP login session.",
        request=ClientSendOTPSerializer,
        responses={
            200: OpenApiResponse(description="OTP session created successfully."),
            400: OpenApiResponse(description="Invalid phone number or request payload."),
        },
    ),
)(ClientSendOTPAPIView)

ClientVerifyOTPAPIView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - User"],
        summary="Verify login OTP",
        description="Verifies the latest unused OTP for the phone number and returns JWT access and refresh tokens.",
        request=ClientVerifyOTPSerializer,
        responses={
            200: OpenApiResponse(description="OTP verified. JWT tokens and user profile returned."),
            400: OpenApiResponse(description="OTP not found, expired, already used, or invalid."),
        },
    ),
)(ClientVerifyOTPAPIView)

AdminLoginAPIView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - Admin"],
        summary="Admin login",
        description="Authenticates a staff/admin user with phone number and password. Returns JWT access and refresh tokens.",
        request=AdminLoginSerializer,
        responses={
            200: OpenApiResponse(description="Admin authenticated successfully."),
            400: OpenApiResponse(description="Invalid credentials or user is not staff."),
        },
    ),
)(AdminLoginAPIView)

CustomTokenRefreshView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - Token"],
        summary="Refresh JWT token",
        description="Accepts a valid refresh token and returns a fresh access token.",
        request=TokenRefreshSerializer,
        responses={
            200: OpenApiResponse(description="Token refreshed successfully."),
            401: OpenApiResponse(description="Refresh token is invalid or expired."),
        },
    ),
)(CustomTokenRefreshView)

CustomTokenVerifyView = extend_schema_view(
    post=extend_schema(
        tags=["Auth - Token"],
        summary="Verify JWT token",
        description="Checks whether a JWT token is currently valid.",
        request=TokenVerifySerializer,
        responses={
            200: OpenApiResponse(description="Token is valid."),
            401: OpenApiResponse(description="Token is invalid or expired."),
        },
    ),
)(CustomTokenVerifyView)

CurrentUserAPIView = extend_schema_view(
    get=extend_schema(
        tags=["User Account"],
        summary="Get current user",
        description="Returns the authenticated user's profile, subscription state, and related onboarding metadata.",
        responses={200: CurrentUserSerializer, 401: OpenApiResponse(description="Authentication required.")},
    ),
    patch=extend_schema(
        tags=["User Account"],
        summary="Update current user",
        description="Partially updates the authenticated user's profile fields.",
        request=CurrentUserSerializer,
        responses={200: CurrentUserSerializer, 400: OpenApiResponse(description="Invalid profile data.")},
    ),
    delete=extend_schema(
        tags=["User Account"],
        summary="Delete current user",
        description="Deletes the authenticated user account.",
        responses={200: OpenApiResponse(description="User account deleted successfully.")},
    ),
)(CurrentUserAPIView)

CurrentUserPlanAndProgressAPIView = extend_schema_view(
    get=extend_schema(
        tags=["User Plan Progress"],
        summary="Get plan and onboarding progress",
        description="Returns the paid subscription status and current setup progress for the authenticated user.",
        responses={
            200: OpenApiResponse(description="Plan and progress returned successfully."),
            404: OpenApiResponse(description="No active paid subscription found."),
        },
    ),
)(CurrentUserPlanAndProgressAPIView)
