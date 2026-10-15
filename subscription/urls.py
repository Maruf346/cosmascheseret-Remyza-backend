from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminMonthlyRevenueAPIView,
    AdminRevenueAnalyticsAPIView,
    AdminSubscriberDetailAPIView,
    AdminSubscriberListAPIView,
    AdminUserAnalyticsAPIView,
    UserSubscriptionViewSet,
)


router = DefaultRouter()
router.register("user-subscription", UserSubscriptionViewSet, basename="user-subscription")

urlpatterns = [
    path("admin/subscriptions/", AdminSubscriberListAPIView.as_view(), name="admin-subscriber-list"),
    path("admin/subscriptions/<int:user_id>/", AdminSubscriberDetailAPIView.as_view(), name="admin-subscriber-detail"),
    path("admin/revenue/monthly/", AdminMonthlyRevenueAPIView.as_view(), name="admin-monthly-revenue"),
    path("admin/revenue/analytics/", AdminRevenueAnalyticsAPIView.as_view(), name="admin-revenue-analytics"),
    path("admin/users/analytics/", AdminUserAnalyticsAPIView.as_view(), name="admin-user-analytics"),
    path("", include(router.urls)),
]
