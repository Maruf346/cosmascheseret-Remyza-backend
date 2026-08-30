from django.urls import path

from .views import *

urlpatterns = [
    path("sentdm/account/check/", SentDMAccountCheckAPIView.as_view(), name="sentdm-account-check"),
    path("sentdm/profiles/", SentDMProfileListAPIView.as_view(), name="sentdm-profile-list"),
    path("sentdm/profiles/create/", SentDMProfileCreateAPIView.as_view(), name="sentdm-profile-create"),
    path("sentdm/profiles/current/", SentDMCurrentProfileAPIView.as_view(), name="sentdm-profile-current"),
    path("sentdm/profiles/complete/", SentDMProfileCompleteAPIView.as_view(), name="sentdm-profile-complete"),
    path("sentdm/messages/send-sandbox/", SentDMSendSandboxMessageAPIView.as_view(), name="sentdm-message-send-sandbox"),
    # Enable only after Sent.dm live credentials, approved Sender Profiles, webhook secret,
    # and real lead/conversation routing are ready. Then retire send-sandbox from client usage.
    # path("sentdm/messages/send/", SentDMSendMessageAPIView.as_view(), name="sentdm-message-send"),
    path("sentdm/webhooks/inbound/", SentDMInboundWebhookAPIView.as_view(), name="sentdm-inbound-webhook"),
    path("sentdm/webhooks/profile-ready/", SentDMProfileReadyWebhookAPIView.as_view(), name="sentdm-profile-ready-webhook"),
]