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
