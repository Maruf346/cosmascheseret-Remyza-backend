from django.urls import path

from .views import StructuredMessageAPIView

urlpatterns = [
    path("ai/messages/structure/", StructuredMessageAPIView.as_view(), name="ai-message-structure"),
]