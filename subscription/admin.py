from django.contrib import admin
from django.utils import timezone

from .choices import SubscriptionStatus
from .models import UserSubscription


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "organization",
        "medium",
        "product_id",
        "plan_type",
        "is_subscription_active",
        "store_status",
        "store_environment",
        "expiry_date",
        "created_at",
    )
    list_filter = ("medium", "is_subscription_active", "store_environment", "store_status", "created_at")
    search_fields = (
        "user__email",
        "user__phone_number",
        "user__full_name",
        "organization__name",
        "product_id",
        "plan_type",
        "purchase_token",
        "transaction_id",
        "original_transaction_id",
        "order_id",
    )
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("uuid", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25
    fieldsets = (
        ("User", {"fields": ("user", "organization")}),
        ("Store Purchase", {"fields": (
            "medium", "product_id", "plan_type", "purchase_token", "transaction_id",
            "original_transaction_id", "order_id", "store_environment", "store_status",
        )}),
        ("Subscription Status", {"fields": (
            "is_subscription_active", "purchase_date", "expiry_date",
        )}),
        ("Amount", {"fields": ("amount", "currency_code")}),
        ("Store Payload", {"classes": ("collapse",), "fields": ("verification_payload", "app_bundle_id")} ),
        ("System", {"classes": ("collapse",), "fields": ("uuid", "created_at", "updated_at")} ),
    )

    def save_model(self, request, obj, form, change):
        if obj.user and not obj.organization and hasattr(obj.user, "organization"):
            obj.organization = obj.user.organization

        if not obj.start_date:
            obj.start_date = timezone.now()

        if not obj.purchase_date:
            obj.purchase_date = obj.start_date

        obj.expires_at = obj.expiry_date
        obj.status = SubscriptionStatus.ACTIVE if obj.is_subscription_active else SubscriptionStatus.AWAITING_PAYMENT
        super().save_model(request, obj, form, change)