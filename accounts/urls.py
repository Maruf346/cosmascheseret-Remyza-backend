from django.urls import path
from .views import (
    ClientSendOTPAPIView,
    ClientVerifyOTPAPIView,
    AdminLoginAPIView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    
    CurrentUserAPIView,
    ClaimFreeTrailNumber,
)

urlpatterns = [
    path("client/auth/send-otp/", ClientSendOTPAPIView.as_view(), name="client-send-otp"),
    path("client/auth/verify-otp/", ClientVerifyOTPAPIView.as_view(), name="client-verify-otp"),
    path("admin/auth/login/", AdminLoginAPIView.as_view(), name="admin-auth-login"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", CustomTokenVerifyView.as_view(), name="token-verify"),
    
    path("me/", CurrentUserAPIView.as_view(), name="user-info"),
    path("me/cliam-free-trail-number/", ClaimFreeTrailNumber.as_view(), name="claim-user-free-trail"),
]