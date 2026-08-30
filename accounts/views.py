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
from .choices import OTPPurpose
from .models import OTPVerification, User

from business.serializers import OrganizationSerializer, ProviderAccountSerializer
from business.models import PhoneNumber
from .serializers import (
    AdminLoginSerializer,
    ClientSendOTPSerializer,
    ClientVerifyOTPSerializer,
    CurrentUserSerializer,
)
from django.db import transaction



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

class CurrentUserPlanAndProgressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def add_progress(self, title, completed):
        weight = int(100 / self.progress["total_steps"])
        if completed:
            self.progress["completed_steps"] += 1

        self.progress["steps"].append({
            "title": title,
            "completed": completed,
            "percentage": weight,
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress = {
            "total_steps": 5,
            "completed_steps": 0,
            "percentage": 0,
            "steps": []
        }
        self.response = {}

    def get_active_subscription(self, user):
        return SubscriptionValidationService.get_paid_active_subscription(user)
    
    def process_subscription(self, subscription):
        self.response.update({
            "plan_type": subscription.plan_type,
            "expires_at": subscription.expiry_date,
            "active_subscription": UserSubscriptionSerializer(subscription).data,
        })
        self.add_progress(
            "Subscription Activated",
            True
        )

    def process_organization(self, user):
        self.organization = getattr(user, "organization", None)
        if self.organization:
            self.response["organization"] = OrganizationSerializer(self.organization).data
        else:
            self.response["organization"] = None

        self.add_progress(
            "Organization Created",
            self.organization is not None,
        )
        return self.organization

    def process_provider_account(self, user):
        self.provider_account = getattr(user, "provider_account", None)
        if self.provider_account:
            self.response["provider_account"] = ProviderAccountSerializer(self.provider_account).data
        else:
            self.response["provider_account"] = None

        self.add_progress(
            "Provider Connected",
            self.provider_account is not None,
        )
        return self.provider_account

    def process_phone_numbers(self):
        self.phone_numbers = PhoneNumber.objects.none()
        if self.organization and self.provider_account:
            self.phone_numbers = PhoneNumber.objects.filter(
                organization=self.organization,
                provider=self.provider_account,
            ).prefetch_related("tfv_verification")
        self.response["phone_numbers"] = [
            {
                "id": phone.id,
                "phone_number": phone.phone_number,
                "status": phone.status,
            }
            for phone in self.phone_numbers
        ]

        self.add_progress(
            "Phone Number Purchased",
            self.phone_numbers.exists(),
        )
        return self.phone_numbers

    def process_tfv(self):
        tfv = None

        if self.phone_numbers.exists():
            tfv = getattr(
                self.phone_numbers.first(),
                "tfv_verification",
                None,
            )

        if tfv:
            self.response["tfv_verification"] = {
                "id": tfv.id,
                "customer_profile_sid": tfv.customer_profile_sid,
                "status": tfv.status,
                "is_expired": tfv.is_expired,
                "is_released": tfv.is_released,
            }

        else:
            self.response["tfv_verification"] = None

        # completed = bool(tfv and tfv.is_verified == "APPROVED")
        completed = bool(tfv and tfv.is_verified == True)
        self.add_progress(
            "TFV Approved",
            completed,
        )

    def finalize_progress(self):
        self.progress["percentage"] = int(
            self.progress["completed_steps"] * 100
            / self.progress["total_steps"]
        )

        self.response["progress"] = self.progress

    def get(self, request):

        subscription = self.get_active_subscription(request.user)

        if not subscription:
            return Response(
                {
                    "success": False,
                    "message": "No active subscription found.",
                    "data": {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        self.process_subscription(subscription)
        self.process_organization(request.user)
        self.process_provider_account(request.user)
        self.process_phone_numbers()
        self.process_tfv()
        self.finalize_progress()

        return Response({
            "success": True,
            "message": "User plan and progress retrieved successfully.",
            "data": self.response,
        })

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
