from django.urls import path, include
from .views import (
    BusinessPhoneNumberSetupAPIViewSets, BusinessProfileSetupAPIView, BusinessSubAccountSyncAPIView, UserBusinessSettingAPIView, UserBusinessOnboardingAPIView, UserBusinessProfileAPIView, UserNotificationSettingsViewSet, BusinessSubAccountSetupAPIView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"notification-settings", UserNotificationSettingsViewSet, basename="notification-settings",)

router_business = DefaultRouter()
router_business.register(r"phone-number", BusinessPhoneNumberSetupAPIViewSets, basename="business-phone-number")



urlpatterns = [
    path("business/profile/setup/", BusinessProfileSetupAPIView.as_view(), name="business-profile-setup",),
    path("me/business-profile/", UserBusinessProfileAPIView.as_view(), name="user-business-profile"),
    path("me/business-settings/", UserBusinessSettingAPIView.as_view(), name="update-business-settings"),
    path("me/onboarding-status/", UserBusinessOnboardingAPIView.as_view(), name="onboarding-status"),

    path("business/sub-account/setup/", BusinessSubAccountSetupAPIView.as_view(), name="business-subaccount-setup"),
    path("business/sub-account/sync/", BusinessSubAccountSyncAPIView.as_view(), name="business-subaccount-sync"),


    
    
    path("business/", include(router_business.urls)),
    
    path("me/", include(router.urls)),
    
]
