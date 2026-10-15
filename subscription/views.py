from calendar import month_abbr
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from accounts.choices import UserType
from accounts.models import User
from common.choices import Status
from crm.choices import LeadStage
from crm.models import Lead
from sentdm.choices import SentDMMessageDirection
from sentdm.models import SentDMMessage
from .models import UserSubscription
from .serializers import (
    AdminMonthlyRevenueResponseSerializer,
    AdminRevenueAnalyticsResponseSerializer,
    AdminSubscriberDetailResponseSerializer,
    AdminSubscriberListResponseSerializer,
    AdminUserAnalyticsResponseSerializer,
    UserSubscriptionListResponseSerializer,
    UserSubscriptionSerializer,
)


class UserSubscriptionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminSubscriptionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminSubscriptionAnalyticsMixin:
    default_currency = "USD"

    def active_subscription_filter(self, now=None):
        now = now or timezone.now()
        return (
            Q(is_subscription_active=True)
            & (Q(expiry_date__isnull=True) | Q(expiry_date__gt=now))
        ) | (
            Q(status="active")
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        )

    def paid_subscription_filter(self, now=None):
        return self.active_subscription_filter(now) & ~Q(plan_type__iexact="trial") & ~Q(plan_type__iexact="free_trial") & ~Q(status="trial")

    def trial_subscription_filter(self):
        return Q(plan_type__iexact="trial") | Q(plan_type__iexact="free_trial") | Q(status="trial") | Q(plan__plan_type="free_trial")

    def get_month_bounds(self, base_date=None):
        now = base_date or timezone.now()
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_end = current_start
        previous_month = current_start.month - 1 or 12
        previous_year = current_start.year if current_start.month > 1 else current_start.year - 1
        previous_start = current_start.replace(year=previous_year, month=previous_month)
        return current_start, previous_start, previous_end

    def percent_change(self, current, previous):
        current = Decimal(current or 0)
        previous = Decimal(previous or 0)
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(float(((current - previous) / previous) * Decimal("100")), 2)

    def money_sum(self, queryset):
        return queryset.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2))
        )["total"] or Decimal("0.00")

    def revenue_queryset(self):
        return UserSubscription.objects.filter(amount__isnull=False)

    def get_revenue_for_range(self, start=None, end=None):
        queryset = self.revenue_queryset()
        if start:
            queryset = queryset.filter(Q(purchase_date__gte=start) | Q(purchase_date__isnull=True, created_at__gte=start))
        if end:
            queryset = queryset.filter(Q(purchase_date__lt=end) | Q(purchase_date__isnull=True, created_at__lt=end))
        return self.money_sum(queryset)

    def get_active_subscribers_count_for_range(self, start=None, end=None):
        queryset = UserSubscription.objects.filter(self.active_subscription_filter())
        if start:
            queryset = queryset.filter(created_at__gte=start)
        if end:
            queryset = queryset.filter(created_at__lt=end)
        return queryset.values("user_id").distinct().count()

    def get_trial_users_count_for_range(self, start=None, end=None):
        queryset = UserSubscription.objects.filter(self.trial_subscription_filter())
        if start:
            queryset = queryset.filter(created_at__gte=start)
        if end:
            queryset = queryset.filter(created_at__lt=end)
        return queryset.values("user_id").distinct().count()

    def get_suspended_users_count_for_range(self, start=None, end=None):
        queryset = User.objects.filter(is_staff=False, is_superuser=False).exclude(status=Status.ACTIVE)
        if start:
            queryset = queryset.filter(created_at__gte=start)
        if end:
            queryset = queryset.filter(created_at__lt=end)
        return queryset.count()

    def get_summary(self):
        current_start, previous_start, previous_end = self.get_month_bounds()
        total_revenue = self.money_sum(self.revenue_queryset())
        current_revenue = self.get_revenue_for_range(current_start)
        previous_revenue = self.get_revenue_for_range(previous_start, previous_end)

        active_subscribers = UserSubscription.objects.filter(self.active_subscription_filter()).values("user_id").distinct().count()
        current_active = self.get_active_subscribers_count_for_range(current_start)
        previous_active = self.get_active_subscribers_count_for_range(previous_start, previous_end)

        trial_users = UserSubscription.objects.filter(self.trial_subscription_filter()).values("user_id").distinct().count()
        current_trial = self.get_trial_users_count_for_range(current_start)
        previous_trial = self.get_trial_users_count_for_range(previous_start, previous_end)

        suspended_users = User.objects.filter(is_staff=False, is_superuser=False).exclude(status=Status.ACTIVE).count()
        current_suspended = self.get_suspended_users_count_for_range(current_start)
        previous_suspended = self.get_suspended_users_count_for_range(previous_start, previous_end)

        return {
            "total_revenue": {
                "value": total_revenue,
                "change_percent": self.percent_change(current_revenue, previous_revenue),
            },
            "active_subscribers": {
                "value": active_subscribers,
                "change_percent": self.percent_change(current_active, previous_active),
            },
            "trial_users": {
                "value": trial_users,
                "change_percent": self.percent_change(current_trial, previous_trial),
            },
            "suspended_users": {
                "value": suspended_users,
                "change_percent": self.percent_change(current_suspended, previous_suspended),
            },
        }

    def get_latest_subscription(self, user):
        return user.subscriptions.order_by("-is_subscription_active", "-expiry_date", "-created_at").first()

    def get_user_plan(self, subscription):
        if not subscription:
            return "free"
        plan_value = (subscription.plan_type or "").strip().lower()
        if subscription.status == "trial" or plan_value in {"trial", "free_trial", "free trail"}:
            return "trial"
        if subscription.is_active:
            return "pro"
        return "free"

    def get_billing_label(self, subscription):
        if not subscription:
            return "Free"
        plan = self.get_user_plan(subscription)
        if plan == "trial":
            return "14 days free"
        amount = subscription.amount
        currency = subscription.currency_code or self.default_currency
        if amount is None:
            return "$79/month" if plan == "pro" else "Free"
        symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
        return f"{symbol}{amount}/month"

    def build_profile_picture_url(self, user, request):
        if not user.profile_picture:
            return None
        url = user.profile_picture.url
        return request.build_absolute_uri(url) if request else url

    def get_lifetime_spent(self, user):
        return self.money_sum(UserSubscription.objects.filter(user=user, amount__isnull=False))

    def serialize_subscriber(self, user, request, include_detail=False):
        subscription = self.get_latest_subscription(user)
        data = {
            "id": user.id,
            "user_id": user.id,
            "name": user.full_name,
            "email": user.email,
            "profile_pic": self.build_profile_picture_url(user, request),
            "plan": self.get_user_plan(subscription),
            "billing": self.get_billing_label(subscription),
            "is_active": user.status == Status.ACTIVE,
            "joined_at": user.created_at,
        }
        if include_detail:
            data.update(
                {
                    "phone_number": user.phone_number,
                    "status": user.status,
                    "next_billing_cycle": (
                        subscription.next_billing_date
                        or subscription.expiry_date
                        or subscription.expires_at
                        if subscription
                        else None
                    ),
                    "lifetime_spent": self.get_lifetime_spent(user),
                    "currency": (subscription.currency_code if subscription else "") or self.default_currency,
                    "subscription_id": subscription.id if subscription else None,
                    "product_id": subscription.product_id if subscription else "",
                    "store_status": subscription.store_status if subscription else "",
                    "subscription_started_at": subscription.start_date if subscription else None,
                    "subscription_expires_at": (subscription.expiry_date or subscription.expires_at) if subscription else None,
                }
            )
        return data

    def subscriber_queryset(self):
        return (
            User.objects
            .filter(is_staff=False, is_superuser=False)
            .prefetch_related("subscriptions")
            .order_by("-created_at")
        )

    def get_period_range(self, request):
        now = timezone.now()
        period = (request.query_params.get("period") or "this_month").strip().lower()
        if period == "this_week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif period == "this_quarter":
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_month = quarter_month + 3
            if end_month > 12:
                end = start.replace(year=start.year + 1, month=end_month - 12)
            else:
                end = start.replace(month=end_month)
        elif period == "this_year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1)
        elif period == "custom":
            from_value = parse_date(request.query_params.get("from_date") or "")
            to_value = parse_date(request.query_params.get("to_date") or "")
            if not from_value or not to_value:
                raise ValueError("from_date and to_date are required for custom range.")
            if to_value < from_value:
                raise ValueError("to_date must be after or equal to from_date.")
            start = timezone.make_aware(datetime.combine(from_value, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(to_value + timedelta(days=1), datetime.min.time()))
        else:
            raise ValueError("period must be one of this_week, this_month, this_quarter, this_year, or custom.")
        return period, start, end

    def get_previous_range(self, start, end):
        duration = end - start
        return start - duration, start

    def count_users_for_range(self, start, end):
        return User.objects.filter(
            is_staff=False,
            is_superuser=False,
            created_at__gte=start,
            created_at__lt=end,
        ).count()

    def count_messages_for_range(self, start, end):
        return SentDMMessage.objects.filter(
            direction=SentDMMessageDirection.OUTBOUND,
            created_at__gte=start,
            created_at__lt=end,
        ).count()

    def lead_conversion_percent_for_range(self, start, end):
        leads = Lead.objects.filter(created_at__gte=start, created_at__lt=end)
        total = leads.count()
        if total == 0:
            return Decimal("0.00")
        converted = leads.filter(stage=LeadStage.CONVERTED).count()
        return Decimal(converted * 100) / Decimal(total)

    def percent_share(self, count, total):
        if total == 0:
            return 0.0
        return round(float(Decimal(count) * Decimal("100") / Decimal(total)), 2)

    def get_bucket_step(self, period, start, end):
        days = (end - start).days
        if period == "this_week":
            return "day"
        if period == "this_year":
            return "month"
        if period == "this_month" or days <= 31:
            return "day"
        return "week"

    def iter_message_buckets(self, period, start, end):
        step = self.get_bucket_step(period, start, end)
        current = start
        buckets = []
        while current < end:
            if step == "month":
                next_month = current.month + 1
                next_year = current.year
                if next_month == 13:
                    next_month = 1
                    next_year += 1
                bucket_end = current.replace(year=next_year, month=next_month)
                label = month_abbr[current.month]
            elif step == "week":
                bucket_end = min(current + timedelta(days=7), end)
                label = f"{current.strftime('%b %d')}-{(bucket_end - timedelta(days=1)).strftime('%b %d')}"
            else:
                bucket_end = min(current + timedelta(days=1), end)
                label = current.strftime("%a").lower() if period == "this_week" else current.strftime("%b %d")
            buckets.append(
                {
                    "label": label,
                    "message_volume": self.count_messages_for_range(current, bucket_end),
                }
            )
            current = bucket_end
        return buckets

    def get_subscriber_breakdown(self):
        normal_users = User.objects.filter(is_staff=False, is_superuser=False)
        total_users = normal_users.count()
        pro_user_ids = set(
            UserSubscription.objects
            .filter(self.paid_subscription_filter())
            .values_list("user_id", flat=True)
            .distinct()
        )
        trial_user_ids = set(
            UserSubscription.objects
            .filter(self.trial_subscription_filter())
            .values_list("user_id", flat=True)
            .distinct()
        )
        total_subscribers = len(pro_user_ids | trial_user_ids)
        trial_or_free_count = max(total_users - len(pro_user_ids), 0)
        return [
            {"label": "total_subscribers", "count": total_subscribers, "percent": self.percent_share(total_subscribers, total_users)},
            {"label": "pro_subscribers", "count": len(pro_user_ids), "percent": self.percent_share(len(pro_user_ids), total_users)},
            {"label": "trial_or_free_users", "count": trial_or_free_count, "percent": self.percent_share(trial_or_free_count, total_users)},
        ]

    def get_lead_breakdown(self, start, end, previous_start, previous_end):
        leads = Lead.objects.filter(created_at__gte=start, created_at__lt=end)
        previous_leads = Lead.objects.filter(created_at__gte=previous_start, created_at__lt=previous_end)
        total = leads.count()
        previous_total = previous_leads.count()
        items = []
        for label, stage in (("hot_leads", LeadStage.HOT), ("warm_leads", LeadStage.WARM), ("cold_leads", LeadStage.COLD)):
            count = leads.filter(stage=stage).count()
            items.append({"label": label, "count": count, "percent": self.percent_share(count, total)})
        items.append(
            {
                "label": "total_leads",
                "count": total,
                "percent": 100.0 if total else 0.0,
                "change_percent": self.percent_change(total, previous_total),
            }
        )
        return items


class UserSubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = UserSubscriptionPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return UserSubscription.objects.none()

        queryset = (
            UserSubscription.objects
            .select_related("user", "organization")
            .order_by("-created_at")
        )

        user = self.request.user
        if user.is_staff or user.is_superuser or user.user_type == UserType.ADMIN:
            return queryset
        return queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save()


class AdminSubscriberListAPIView(AdminSubscriptionAnalyticsMixin, APIView):
    permission_classes = [IsAdminUser]
    pagination_class = AdminSubscriptionPagination

    @extend_schema(
        tags=["Admin - Subscriptions"],
        summary="List subscribers and subscription revenue summary",
        description="Returns admin subscription dashboard metrics and a paginated subscriber list with plan, billing, active status, and joined date.",
        parameters=[
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
        ],
        responses={200: AdminSubscriberListResponseSerializer},
    )
    def get(self, request):
        queryset = self.subscriber_queryset()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        results = [self.serialize_subscriber(user, request) for user in page]
        data = {
            "summary": self.get_summary(),
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": results,
        }
        return Response({"success": True, "data": data})


class AdminSubscriberDetailAPIView(AdminSubscriptionAnalyticsMixin, APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin - Subscriptions"],
        summary="Get subscriber details",
        description="Returns one subscriber with plan, billing, next billing cycle, and lifetime spent amount.",
        responses={200: AdminSubscriberDetailResponseSerializer, 404: OpenApiResponse(description="Subscriber not found.")},
    )
    def get(self, request, user_id):
        try:
            user = self.subscriber_queryset().get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Subscriber not found."}, status=404)
        return Response({"success": True, "data": self.serialize_subscriber(user, request, include_detail=True)})


class AdminMonthlyRevenueAPIView(AdminSubscriptionAnalyticsMixin, APIView):
    permission_classes = [IsAdminUser]

    def iter_last_six_months(self):
        current = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        months = []
        for index in range(5, -1, -1):
            month = current.month - index
            year = current.year
            while month <= 0:
                month += 12
                year -= 1
            start = current.replace(year=year, month=month)
            next_month = month + 1
            next_year = year
            if next_month == 13:
                next_month = 1
                next_year += 1
            end = start.replace(year=next_year, month=next_month)
            months.append((start, end))
        return months

    @extend_schema(
        tags=["Admin - Revenue"],
        summary="Get monthly revenue",
        description="Returns revenue totals for the last six calendar months.",
        responses={200: AdminMonthlyRevenueResponseSerializer},
    )
    def get(self, request):
        data = [
            {
                "month": month_abbr[start.month],
                "year": start.year,
                "revenue": self.get_revenue_for_range(start, end),
                "currency": self.default_currency,
            }
            for start, end in self.iter_last_six_months()
        ]
        return Response({"success": True, "data": data})


class AdminRevenueAnalyticsAPIView(AdminSubscriptionAnalyticsMixin, APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin - Revenue"],
        summary="Get revenue analytics",
        description=(
            "Returns filtered revenue analytics for this week, this month, this quarter, this year, "
            "or a custom date range. Custom ranges require `from_date` and `to_date` in YYYY-MM-DD format."
        ),
        parameters=[
            OpenApiParameter(
                "period",
                str,
                required=False,
                description="One of `this_week`, `this_month`, `this_quarter`, `this_year`, or `custom`.",
            ),
            OpenApiParameter("from_date", str, required=False, description="Custom range start date in YYYY-MM-DD format."),
            OpenApiParameter("to_date", str, required=False, description="Custom range end date in YYYY-MM-DD format."),
        ],
        responses={
            200: AdminRevenueAnalyticsResponseSerializer,
            400: OpenApiResponse(description="Invalid period or custom date range."),
        },
    )
    def get(self, request):
        try:
            period, start, end = self.get_period_range(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        previous_start, previous_end = self.get_previous_range(start, end)
        current_new_users = self.count_users_for_range(start, end)
        previous_new_users = self.count_users_for_range(previous_start, previous_end)
        current_revenue = self.get_revenue_for_range(start, end)
        previous_revenue = self.get_revenue_for_range(previous_start, previous_end)
        current_messages = self.count_messages_for_range(start, end)
        previous_messages = self.count_messages_for_range(previous_start, previous_end)
        current_conversion = self.lead_conversion_percent_for_range(start, end)
        previous_conversion = self.lead_conversion_percent_for_range(previous_start, previous_end)

        data = {
            "period": period,
            "start_date": start.date(),
            "end_date": (end - timedelta(days=1)).date(),
            "summary": {
                "new_users": {
                    "value": current_new_users,
                    "change_percent": self.percent_change(current_new_users, previous_new_users),
                },
                "revenue": {
                    "value": current_revenue,
                    "change_percent": self.percent_change(current_revenue, previous_revenue),
                },
                "messages_sent": {
                    "value": current_messages,
                    "change_percent": self.percent_change(current_messages, previous_messages),
                },
                "lead_conversion_percent": {
                    "value": current_conversion,
                    "change_percent": self.percent_change(current_conversion, previous_conversion),
                },
            },
            "message_volume_analytics": self.iter_message_buckets(period, start, end),
            "subscribers": self.get_subscriber_breakdown(),
            "leads": self.get_lead_breakdown(start, end, previous_start, previous_end),
        }
        return Response({"success": True, "data": data})


class AdminUserAnalyticsAPIView(AdminSubscriptionAnalyticsMixin, APIView):
    permission_classes = [IsAdminUser]

    def parse_year(self, raw_year):
        now = timezone.now()
        value = (raw_year or "this_year").strip().lower()
        if value == "this_year":
            return now.year
        if value == "last_year":
            return now.year - 1
        try:
            year = int(value)
        except (TypeError, ValueError):
            return now.year
        return year

    @extend_schema(
        tags=["Admin - Users"],
        summary="Get admin user analytics",
        description="Returns user dashboard summary metrics and monthly user signup counts for the requested year.",
        parameters=[
            OpenApiParameter(
                "year",
                str,
                required=False,
                description="Use `this_year`, `last_year`, or a numeric year such as `2024`.",
            ),
        ],
        responses={200: AdminUserAnalyticsResponseSerializer},
    )
    def get(self, request):
        year = self.parse_year(request.query_params.get("year"))
        current_start, _, _ = self.get_month_bounds()
        user_queryset = User.objects.filter(is_staff=False, is_superuser=False)
        summary = {
            "total_users": user_queryset.count(),
            "active_subscriptions": UserSubscription.objects.filter(self.active_subscription_filter()).values("user_id").distinct().count(),
            "monthly_revenue": self.get_revenue_for_range(current_start),
            "total_leads_captured": Lead.objects.count(),
        }
        ratio = []
        for month in range(1, 13):
            start = timezone.make_aware(datetime(year, month, 1))
            if month == 12:
                end = timezone.make_aware(datetime(year + 1, 1, 1))
            else:
                end = timezone.make_aware(datetime(year, month + 1, 1))
            ratio.append(
                {
                    "month": month_abbr[month],
                    "year": year,
                    "users": user_queryset.filter(created_at__gte=start, created_at__lt=end).count(),
                }
            )
        return Response({"success": True, "data": {"summary": summary, "year": year, "user_ratio": ratio}})


UserSubscriptionViewSet = extend_schema_view(
    list=extend_schema(
        tags=["User Subscriptions"],
        summary="List user subscriptions",
        description=(
            "Returns Apple/Google subscription payment records. Admin users see all users; "
            "client users see only their own records."
        ),
        parameters=[
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
        ],
        responses={200: UserSubscriptionListResponseSerializer},
    ),
    retrieve=extend_schema(
        tags=["User Subscriptions"],
        summary="Get user subscription details",
        description=(
            "Returns one Apple/Google subscription payment record. Admin users can retrieve any record; "
            "client users can retrieve only their own records."
        ),
        responses={200: UserSubscriptionSerializer, 404: OpenApiResponse(description="Subscription record not found.")},
    ),
    create=extend_schema(
        tags=["User Subscriptions"],
        summary="Create subscription payment record",
        description=(
            "Stores an Apple or Google in-app subscription payment record sent by the mobile app. "
            "The backend stores the record and uses active, unexpired records to unlock paid messaging."
        ),
        request=UserSubscriptionSerializer,
        responses={201: UserSubscriptionSerializer, 400: OpenApiResponse(description="Invalid Apple/Google subscription payload.")},
    ),
)(UserSubscriptionViewSet)
