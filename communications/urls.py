from django.urls import path

from .views import WelcomeMessagePresetAPIView, WelcomeMessageTemplateAPIView

urlpatterns = [
    path("welcome-message/", WelcomeMessagePresetAPIView.as_view(), name="welcome-message-preset"),
    # Legacy free-form endpoint intentionally disabled for compliance safety.
    # path("message-templates/welcome/", WelcomeMessageTemplateAPIView.as_view(), name="welcome-message-template"),
]