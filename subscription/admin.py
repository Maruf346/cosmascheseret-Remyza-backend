from django.contrib import admin

from .models import (
    SubscriptionPlan, UserSubscription,
    Payment, Invoice, PurchaseInfo,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "plan_type", "billing_type", "price", "currency", "lead_limit", "phone_number_limit", "is_active", "created_at")
    list_filter = ("plan_type", "billing_type", "currency", "is_active", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("price",)
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "plan", "status", "billing_cycle", "auto_renew", "start_date", "expires_at")
    list_filter = ("status", "billing_cycle", "auto_renew", "created_at")
    search_fields = ("organization__name", "plan__name")
    autocomplete_fields = ("organization", "plan")
    list_select_related = ("organization", "plan")
    readonly_fields = ("uuid", "created_at", "updated_at")
    ordering = ("-start_date",)
    date_hierarchy = "start_date"
    list_per_page = 25


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "transaction_id", "amount", "currency", "status", "paid_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("transaction_id", "subscription__organization__name")
    autocomplete_fields = ("subscription",)
    list_select_related = ("subscription",)
    readonly_fields = [field.name for field in Payment._meta.fields]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25

    # def has_add_permission(self, request):
    #     return False

    # def has_change_permission(self, request, obj=None):
    #     return False

    # def has_delete_permission(self, request, obj=None):
    #     return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice_number", "subscription", "total_amount", "currency", "status", "due_date", "paid_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("invoice_number", "subscription__organization__name")
    autocomplete_fields = ("subscription",)
    list_select_related = ("subscription",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-due_date",)
    date_hierarchy = "due_date"
    list_per_page = 25


@admin.register(PurchaseInfo)
class PurchaseInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "transaction_id", "is_active", "expires_at", "created_at")
    list_filter = ("platform", "is_active", "created_at")
    search_fields = ("transaction_id", "original_transaction_id", "product_id", "user__phone_number", "user__email")
    autocomplete_fields = ("user", "payment")
    list_select_related = ("user", "payment")
    readonly_fields = [field.name for field in PurchaseInfo._meta.fields]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # def has_delete_permission(self, request, obj=None):
    #     return False



