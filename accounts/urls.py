from django.urls import path
from .views import (
    ClientSignupAPIView,
    ClientSendOTPAPIView,
    ClientVerifyOTPAPIView,
    AdminLoginAPIView,
    AdminUserDetailAPIView,
    AdminUserExportCSVAPIView,
    AdminUserListAPIView,
    CurrentUserPlanAndProgressAPIView,
    CurrentUserCheseraNumberAPIView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,

    CurrentUserAPIView,
    # Twilio-backed free-trial number claim is disabled during Sent.dm migration.
    # ClaimFreeTrailNumber,
)

urlpatterns = [
    path("client/auth/signup/", ClientSignupAPIView.as_view(), name="client-signup"),
    path("client/auth/send-otp/", ClientSendOTPAPIView.as_view(), name="client-send-otp"),
    path("client/auth/verify-otp/", ClientVerifyOTPAPIView.as_view(), name="client-verify-otp"),
    path("admin/auth/login/", AdminLoginAPIView.as_view(), name="admin-auth-login"),
    path("admin/users/", AdminUserListAPIView.as_view(), name="admin-user-list"),
    path("admin/users/export/", AdminUserExportCSVAPIView.as_view(), name="admin-user-export"),
    path("admin/users/<int:user_id>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", CustomTokenVerifyView.as_view(), name="token-verify"),

    path("me/", CurrentUserAPIView.as_view(), name="user-info"),
    # Twilio-backed free-trial number claim is hidden from Swagger during Sent.dm migration.
    # path("me/claim-free-trail-number/", ClaimFreeTrailNumber.as_view(), name="claim-user-free-trail"),
    path("me/plan-and-progress/", CurrentUserPlanAndProgressAPIView.as_view(), name="user-plan-and-progress"),
    path("me/chesera-number/", CurrentUserCheseraNumberAPIView.as_view(), name="user-chesera-number"),
]
