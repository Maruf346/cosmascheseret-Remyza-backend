import base64
import csv
from datetime import timedelta
from io import BytesIO

import qrcode
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from rest_framework import response
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
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
    AdminLoginResponseSerializer,
    AdminLoginSerializer,
    AdminUserDeleteResponseSerializer,
    AdminUserDetailResponseSerializer,
    AdminUserExportQuerySerializer,
    AdminUserListResponseSerializer,
    AdminUserToggleActiveResponseSerializer,
    AdminUserToggleActiveSerializer,
    ClientSendOTPResponseSerializer,
    ClientSignupSerializer,
    ClientSignupResponseSerializer,
    ClientSendOTPSerializer,
    ClientVerifyOTPSerializer,
    ClientVerifyOTPResponseSerializer,
    CurrentUserSerializer,
    CurrentUserCheseraNumberSerializer,
    CurrentUserCheseraNumberResponseSerializer,
    CurrentUserPlanAndProgressResponseSerializer,
    CurrentUserResponseSerializer,
    CurrentUserUpdateResponseSerializer,
)
from common.choices import Status
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
from subscription.models import UserSubscription
from subscription.serializers import UserSubscriptionSerializer
from core.models import FreeTrailPhoneNumber, UserFreeTrailNumber, PhoneNumberStatus
from django.db.models import Min
from core.model_serializer import UserFreeTrailNumberSerializer


class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminUserManagementMixin:
    export_columns = {
        "user_id": "User ID",
        "full_name": "Full Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "business_name": "Business Name",
        "business_type": "Business Type",
        "plan": "Plan",
        "status": "Status",
        "messages_sent_count": "Messages Sent",
        "leads_count": "Leads Generated",
        "joined_date": "Joined Date",
        "last_active": "Last Active",
        "chesera_number": "Chesera Number",
    }
    default_export_columns = tuple(export_columns.keys())

    def get_base_queryset(self):
        return (
            User.objects
            .filter(is_staff=False, is_superuser=False)
            .select_related("organization", "organization__business_type")
            .annotate(
                leads_count_value=Count("organization__leads", distinct=True),
                messages_sent_count_value=Count(
                    "organization__sentdm_messages",
                    filter=Q(organization__sentdm_messages__direction="outbound"),
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )

    def get_active_subscription(self, user):
        return (
            UserSubscription.objects
            .filter(user=user)
            .order_by("-is_subscription_active", "-expiry_date", "-created_at")
            .first()
        )

    def get_chesera_number(self, user):
        organization = getattr(user, "organization", None)
        profile = getattr(organization, "sentdm_profile", None) if organization else None
        if profile and profile.phone_number:
            return profile.phone_number
        user_profile = getattr(user, "sentdm_profile", None)
        if user_profile and user_profile.phone_number:
            return user_profile.phone_number
        return ""

    def get_plan_price(self, subscription):
        if not subscription:
            return ""
        amount = subscription.amount
        currency = subscription.currency_code or "USD"
        if amount is None:
            return "$84/month" if subscription.is_active else ""
        symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
        return f"{symbol}{amount}/month"

    def get_response_rate(self, user):
        organization = getattr(user, "organization", None)
        if not organization:
            return 0.0
        leads = organization.leads.all()
        total = leads.count()
        if total == 0:
            return 0.0
        responded = leads.filter(last_outgoing_at__isnull=False).count()
        return round((responded / total) * 100, 2)

    def get_days_active(self, user):
        return max((timezone.now() - user.created_at).days, 0)

    def humanize_datetime(self, value):
        if not value:
            return ""
        delta = timezone.now() - value
        seconds = max(int(delta.total_seconds()), 0)
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days} days ago"
        weeks = days // 7
        if weeks < 5:
            return f"{weeks} weeks ago" if weeks > 1 else "1 week ago"
        months = days // 30
        return f"{months} months ago" if months > 1 else "1 month ago"

    def get_user_plan(self, user):
        subscription = self.get_active_subscription(user)
        if subscription and subscription.is_free_trial:
            return "trial"
        if subscription and subscription.is_active:
            return "pro"
        return "free"

    def is_trial_user(self, user):
        subscription = self.get_active_subscription(user)
        if not subscription:
            return False
        return subscription.is_free_trial or (subscription.plan_type or "").lower() in {"trial", "free_trial", "free trail"}

    def get_filtered_queryset(self, request):
        queryset = self.get_base_queryset()
        search = (request.query_params.get("search") or "").strip()
        plan = (request.query_params.get("plan") or "").strip().lower()
        is_active = request.query_params.get("is_active")

        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(email__icontains=search)
                | Q(organization__name__icontains=search)
            )

        if is_active is not None and str(is_active).lower() in {"true", "false"}:
            if str(is_active).lower() == "true":
                queryset = queryset.filter(status=Status.ACTIVE)
            else:
                queryset = queryset.exclude(status=Status.ACTIVE)

        if plan:
            if plan in {"free", "trial"}:
                user_ids = [user.id for user in queryset if self.get_user_plan(user).lower() == plan]
                queryset = queryset.filter(id__in=user_ids)
            elif plan == "pro":
                user_ids = [user.id for user in queryset if self.get_user_plan(user).lower() == "pro"]
                queryset = queryset.filter(id__in=user_ids)
            else:
                queryset = queryset.filter(subscriptions__is_subscription_active=True, subscriptions__plan_type__iexact=plan).distinct()

        return queryset

    def get_summary(self, queryset):
        users = list(queryset)
        return {
            "total_users": len(users),
            "total_active": sum(1 for user in users if user.status == Status.ACTIVE),
            "total_blocked": sum(1 for user in users if user.status != Status.ACTIVE),
            "total_on_trial": sum(1 for user in users if self.is_trial_user(user)),
        }

    def build_profile_picture_url(self, user, request):
        if not user.profile_picture:
            return None
        url = user.profile_picture.url
        return request.build_absolute_uri(url) if request else url

    def serialize_user_list_item(self, user, request):
        organization = getattr(user, "organization", None)
        return {
            "id": user.id,
            "user_id": user.id,
            "user_name": user.full_name,
            "business_name": organization.name if organization else None,
            "profile_pic": self.build_profile_picture_url(user, request),
            "email": user.email,
            "phone": user.phone_number,
            "plan": self.get_user_plan(user),
            "messages_sent_count": getattr(user, "messages_sent_count_value", 0) or 0,
            "leads_count": getattr(user, "leads_count_value", 0) or 0,
            "is_active": user.status == Status.ACTIVE,
            "joined_date": user.created_at,
        }

    def serialize_subscription(self, user):
        subscription = self.get_active_subscription(user)
        if not subscription:
            return None
        return {
            "id": subscription.id,
            "plan": self.get_user_plan(user),
            "price": self.get_plan_price(subscription),
            "plan_type": subscription.plan_type,
            "product_id": subscription.product_id,
            "status": subscription.status,
            "is_active": subscription.is_active,
            "medium": subscription.medium,
            "start_date": subscription.start_date,
            "next_renewal": subscription.expiry_date or subscription.expires_at,
            "purchase_date": subscription.purchase_date,
            "expiry_date": subscription.expiry_date,
        }

    def serialize_user_detail(self, user, request):
        organization = getattr(user, "organization", None)
        business_type = organization.business_type.name if organization and organization.business_type else ""
        timezone_value = user.timezone or (getattr(getattr(organization, "settings", None), "timezone", "") if organization else "")
        return {
            **self.serialize_user_list_item(user, request),
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "city": user.city,
            "country": user.country,
            "country_code": user.country_code,
            "timezone": timezone_value,
            "profile_picture": self.build_profile_picture_url(user, request),
            "user_type": user.user_type,
            "is_phone_verified": user.is_phone_verified,
            "status": user.status,
            "days_active": self.get_days_active(user),
            "response_rate": self.get_response_rate(user),
            "business_type": business_type,
            "chesera_number": self.get_chesera_number(user),
            "last_active": self.humanize_datetime(user.last_activity_at),
            "last_activity_at": user.last_activity_at,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "email": organization.email,
                "website": organization.website,
                "country": organization.country,
                "business_type": business_type,
                "is_onboarding_completed": organization.is_onboarding_completed,
            } if organization else None,
            "subscription": self.serialize_subscription(user),
        }

    def get_export_queryset(self, request):
        queryset = self.get_filtered_queryset(request)
        date_range = (request.query_params.get("date_range") or "all_time").strip().lower()
        now = timezone.now()
        if date_range == "last_week":
            queryset = queryset.filter(created_at__gte=now - timedelta(days=7))
        elif date_range == "last_month":
            queryset = queryset.filter(created_at__gte=now - timedelta(days=30))
        return queryset

    def get_export_columns(self, request):
        raw_columns = (request.query_params.get("columns") or "").strip()
        if not raw_columns:
            return list(self.default_export_columns)
        requested = [column.strip() for column in raw_columns.split(",") if column.strip()]
        valid = [column for column in requested if column in self.export_columns]
        return valid or list(self.default_export_columns)

    def build_export_row(self, user, request):
        list_item = self.serialize_user_list_item(user, request)
        detail = self.serialize_user_detail(user, request)
        return {
            "user_id": list_item["user_id"],
            "full_name": detail["full_name"],
            "email": list_item["email"],
            "phone": list_item["phone"],
            "business_name": list_item["business_name"],
            "business_type": detail["business_type"],
            "plan": list_item["plan"],
            "status": detail["status"],
            "messages_sent_count": list_item["messages_sent_count"],
            "leads_count": list_item["leads_count"],
            "joined_date": list_item["joined_date"],
            "last_active": detail["last_active"],
            "chesera_number": detail["chesera_number"],
        }

    def format_export_value(self, value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if value is None:
            return ""
        return value


class AdminUserListAPIView(AdminUserManagementMixin, APIView):
    permission_classes = [IsAdminUser]
    pagination_class = AdminUserPagination

    @extend_schema(
        tags=["Admin - Users"],
        summary="List users",
        description="Returns a paginated admin user list with summary counts, plan/status filters, and search by name, phone, email, or business.",
        parameters=[
            OpenApiParameter("search", str, required=False, description="Search by user name, phone, email, or business name."),
            OpenApiParameter("plan", str, required=False, description="Filter by plan, for example `free`, `trial`, or `pro`."),
            OpenApiParameter("is_active", bool, required=False, description="Filter active users (`true`) or blocked/inactive users (`false`)."),
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
        ],
        responses={200: AdminUserListResponseSerializer},
    )
    def get(self, request):
        queryset = self.get_filtered_queryset(request)
        summary = self.get_summary(queryset)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        results = [self.serialize_user_list_item(user, request) for user in page]
        return Response(
            {
                "success": True,
                "data": {
                    "summary": summary,
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": results,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminUserExportCSVAPIView(AdminUserManagementMixin, APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin - Users"],
        summary="Export users CSV",
        description="Exports the admin user list as CSV or XLSX using the same search and filters as the list endpoint. Supports delimiter, date range, and selected columns.",
        parameters=[
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("plan", str, required=False),
            OpenApiParameter("is_active", bool, required=False),
            OpenApiParameter("format", str, required=False, description="Export format: `csv` or `xlsx`."),
            OpenApiParameter("delimiter", str, required=False, description="CSV delimiter: `comma`, `semicolon`, or `tab`."),
            OpenApiParameter("date_range", str, required=False, description="Joined-date range: `all_time`, `last_week`, or `last_month`."),
            OpenApiParameter("columns", str, required=False, description="Comma-separated columns to include. Options: user_id, full_name, email, phone, business_name, business_type, plan, status, messages_sent_count, leads_count, joined_date, last_active, chesera_number."),
        ],
        responses={200: OpenApiResponse(description="CSV or XLSX file response.")},
    )
    def get(self, request):
        serializer = AdminUserExportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        queryset = self.get_export_queryset(request)
        columns = self.get_export_columns(request)
        rows = [self.build_export_row(user, request) for user in queryset]

        if serializer.validated_data["format"] == "xlsx":
            return self.build_xlsx_response(columns, rows)

        delimiter_map = {"comma": ",", "semicolon": ";", "tab": "\t"}
        delimiter = delimiter_map[serializer.validated_data["delimiter"]]
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="chesera-users.csv"'
        writer = csv.writer(response, delimiter=delimiter)
        writer.writerow([self.export_columns[column] for column in columns])
        for row in rows:
            writer.writerow([self.format_export_value(row[column]) for column in columns])
        return response

    def build_xlsx_response(self, columns, rows):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Users"
        worksheet.append([self.export_columns[column] for column in columns])
        for row in rows:
            worksheet.append([self.format_export_value(row[column]) for column in columns])

        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="chesera-users.xlsx"'
        return response


class AdminUserDetailAPIView(AdminUserManagementMixin, APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, user_id):
        return self.get_base_queryset().get(pk=user_id)

    @extend_schema(
        tags=["Admin - Users"],
        summary="Get user details",
        description="Returns full admin-facing user details, business profile summary, subscription summary, lead count, and sent-message count.",
        responses={200: AdminUserDetailResponseSerializer, 404: OpenApiResponse(description="User not found.")},
    )
    def get(self, request, user_id):
        try:
            user = self.get_object(user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"success": True, "data": self.serialize_user_detail(user, request)}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Admin - Users"],
        summary="Toggle user active status",
        description="Activates or blocks a user by mapping `is_active=true` to `status=ACTIVE` and `is_active=false` to `status=INACTIVE`.",
        request=AdminUserToggleActiveSerializer,
        responses={200: AdminUserToggleActiveResponseSerializer, 400: OpenApiResponse(description="Invalid payload."), 404: OpenApiResponse(description="User not found.")},
    )
    def patch(self, request, user_id):
        serializer = AdminUserToggleActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = self.get_object(user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        user.status = Status.ACTIVE if serializer.validated_data["is_active"] else Status.INACTIVE
        user.save(update_fields=["status", "updated_at"])
        return Response(
            {
                "success": True,
                "message": "User active status updated successfully.",
                "data": self.serialize_user_detail(user, request),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Admin - Users"],
        summary="Delete user",
        description="Deletes a user account.",
        responses={200: AdminUserDeleteResponseSerializer, 404: OpenApiResponse(description="User not found.")},
    )
    def delete(self, request, user_id):
        try:
            user = self.get_object(user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response({"success": True, "message": "User deleted successfully."}, status=status.HTTP_200_OK)

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

    def build_qr_code_base64(self, payload):
        image = qrcode.make(payload)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @extend_schema(
        tags=["User Chesera Number"],
        summary="Get user's Chesera number",
        description="Returns the authenticated user's dedicated Chesera SMS/RCS number assigned through Sent.dm. Free or pending users receive `assigned=false` with the current activation message.",
        responses={200: CurrentUserCheseraNumberResponseSerializer},
    )
    def get(self, request):
        profile = self.get_profile(request.user)
        number_assignment_status = self.get_number_assignment_status(profile)
        phone_number = profile.phone_number if profile and profile.phone_number else None
        qr_payload = f"sms:{phone_number}" if phone_number else None
        data = {
            "assigned": bool(phone_number),
            "phone_number": phone_number,
            "status": number_assignment_status,
            "number_assignment_status": number_assignment_status,
            "message": self.get_number_assignment_message(number_assignment_status),
            "provider": "sentdm",
            "profile_id": profile.profile_id if profile else None,
            "profile_status": profile.status if profile else None,
            "sms_rcs_active": bool(phone_number and profile.status in ("approved", "active")),
            "qr_payload": qr_payload,
            "qr_code_base64": self.build_qr_code_base64(qr_payload) if qr_payload else None,
        }
        response = Response({"success": True, "data": data}, status=status.HTTP_200_OK)
        if phone_number:
            response["Cache-Control"] = "private, max-age=3600"
        return response

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
            201: ClientSignupResponseSerializer,
            200: ClientSignupResponseSerializer,
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
            200: ClientSendOTPResponseSerializer,
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
            200: ClientVerifyOTPResponseSerializer,
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
            200: AdminLoginResponseSerializer,
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
        responses={200: CurrentUserResponseSerializer, 401: OpenApiResponse(description="Authentication required.")},
    ),
    patch=extend_schema(
        tags=["User Account"],
        summary="Update current user",
        description="Partially updates the authenticated user's profile fields.",
        request=CurrentUserSerializer,
        responses={200: CurrentUserUpdateResponseSerializer, 400: OpenApiResponse(description="Invalid profile data.")},
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
            200: CurrentUserPlanAndProgressResponseSerializer,
            404: OpenApiResponse(description="No active paid subscription found."),
        },
    ),
)(CurrentUserPlanAndProgressAPIView)
