from django.urls import path, include
from .views import (
    BusinessProfileSetupAPIView, UserBusinessSettingAPIView, UserBusinessOnboardingAPIView, UserBusinessProfileAPIView, UserNotificationSettingsViewSet, CreateSubAccountView, 
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"notification-settings", UserNotificationSettingsViewSet, basename="notification-settings",)




urlpatterns = [
    path("business/profile/setup/", BusinessProfileSetupAPIView.as_view(), name="business-profile-setup",),
    path("create-sub-account/", CreateSubAccountView.as_view(), name="create-sub-account"),
    
    path("me/business-profile/", UserBusinessProfileAPIView.as_view(), name="user-business-profile"),
    path("me/business-settings/", UserBusinessSettingAPIView.as_view(), name="update-business-settings"),
    path("me/onboarding-status/", UserBusinessOnboardingAPIView.as_view(), name="onboarding-status"),

    path("me/", include(router.urls)),
    
]
