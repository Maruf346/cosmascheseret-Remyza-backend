from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    BusinessTypeViewSet,
    IndustryViewSet,
    # Twilio/free-trial number routes are disabled while Chesera moves messaging to Sent.dm.
    # FreeTrailPhoneNumberViewSet,
    # TwilioWebhookHandler,
)

router = DefaultRouter()
router.register("business-types", BusinessTypeViewSet, basename="business-type")
router.register("industries", IndustryViewSet, basename="industry")
# Twilio-backed free-trial number inventory is hidden from Swagger during Sent.dm migration.
# router.register("free-trail-number", FreeTrailPhoneNumberViewSet, basename="free-trail-number")

urlpatterns = [
    path("", include(router.urls)),

    # Twilio inbound webhook is hidden from Swagger during Sent.dm migration.
    # path("twilio/webhook/", TwilioWebhookHandler.as_view(), name="twilio-webhook"),
]