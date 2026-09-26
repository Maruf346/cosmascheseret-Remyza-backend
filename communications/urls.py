from django.urls import path

from .views import WelcomeMessageTemplateAPIView

urlpatterns = [
    # path("message-templates/welcome/", WelcomeMessageTemplateAPIView.as_view(), name="welcome-message-template"),
]