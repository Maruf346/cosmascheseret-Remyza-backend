from django.contrib import admin

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