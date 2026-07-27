from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from .choices import OTPPurpose
from .models import OTPVerification, User
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

        has_active_subscription = SubscriptionValidationService.has_active_subscription_with_free_trial(user)
        active_subscription = SubscriptionValidationService.get_active_subscription(user)

        response = {
            "user": serializer.data,
            "has_active_subscription": has_active_subscription,
        }

        if has_active_subscription:
            response["plan_type"] = active_subscription.plan.plan_type,
            response["expires_at"] = active_subscription.expires_at,
            response["active_subscription"] = UserSubscriptionSerializer(active_subscription).data

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

