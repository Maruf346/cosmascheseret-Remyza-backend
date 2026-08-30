from drf_spectacular.openapi import AutoSchema


class TaggedAutoSchema(AutoSchema):
    """Group generated API docs by product workflow instead of /api/v1."""

    TAGS_BY_PREFIX = (
        ("/api/schema/", "API Schema"),
        ("/api/v1/admin/auth/", "Auth - Admin"),
        ("/api/v1/client/auth/", "Auth - User"),
        ("/api/v1/auth/token/", "Auth - Token"),
        ("/api/v1/me/claim-free-trail-number/", "Free Trial"),
        ("/api/v1/me/plan-and-progress/", "User Plan Progress"),
        ("/api/v1/me/business-profile/", "Business"),
        ("/api/v1/me/business-settings/", "Business"),
        ("/api/v1/me/onboarding-status/", "Business"),
        ("/api/v1/me/notification-settings/", "Notifications"),
        ("/api/v1/me/", "User Account"),
        ("/api/v1/business/profile/setup/", "Business"),
        ("/api/v1/business/sub-account/", "Twilio - Subaccounts"),
        ("/api/v1/business/phone-number/verify", "Twilio - Verification"),
        ("/api/v1/business/phone-number/delete", "Twilio - Verification"),
        ("/api/v1/business/phone-number/", "Phone Numbers"),
        ("/api/v1/business-types/", "Reference Data"),
        ("/api/v1/industries/", "Reference Data"),
        ("/api/v1/free-trail-number/{id}/tfv", "Toll-Free Verification"),
        ("/api/v1/free-trail-number/{id}/sms-consent/", "Toll-Free Verification"),
        ("/api/v1/free-trail-number/search-number/", "Trial Numbers"),
        ("/api/v1/free-trail-number/add-trail-number/", "Trial Numbers"),
        ("/api/v1/free-trail-number/create-free-trail-account/", "Trial Numbers"),
        ("/api/v1/free-trail-number/", "Trial Numbers"),
        ("/api/v1/twilio/webhook/", "Twilio - Webhooks"),
        ("/api/v1/sentdm/", "Sent.dm"),
        ("/api/v1/subscription-plans/", "Subscription Plans"),
        ("/api/v1/user-subscription/claim-free-trail/", "Free Trial"),
        ("/api/v1/user-subscription/purchase", "Subscription Purchase"),
        ("/api/v1/user-subscription/current-plan/", "User Subscriptions"),
        ("/api/v1/user-subscription/", "User Subscriptions"),
    )

    APP_TAGS = {
        "accounts": "User Account",
        "business": "Business",
        "core": "Core",
        "subscription": "Subscriptions",
        "communications": "Communications",
        "crm": "CRM",
        "ai": "AI",
        "twilio_app": "Twilio",
        "sentdm": "Sent.dm",
    }

    def get_tags(self):
        path = self.path.lower()

        for prefix, tag in self.TAGS_BY_PREFIX:
            if path.startswith(prefix.lower()):
                return [tag]

        app_label = self.view.__module__.split(".", 1)[0]
        return [self.APP_TAGS.get(app_label, "API")]
