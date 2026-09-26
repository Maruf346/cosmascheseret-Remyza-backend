from django.contrib import admin

from .models import (
    Contact, Lead, LeadActivity, LeadTag, LeadTagAssignment,
)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "contact_number", "email", "business_name", "organization", "source", "linked_lead", "created_at")
    list_filter = ("source", "organization", "created_at")
    search_fields = ("full_name", "contact_number", "phone_number", "email", "business_name", "organization__name")
    autocomplete_fields = ("organization", "linked_lead")
    list_select_related = ("organization", "linked_lead")
    readonly_fields = ("contact_number", "created_at", "updated_at")
    ordering = ("full_name", "-created_at")
    list_per_page = 25


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class LeadTagAssignmentInline(admin.TabularInline):
    model = LeadTagAssignment
    extra = 0
    autocomplete_fields = ("tag",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "contact_number", "organization", "business_phone", "contact", "source", "stage", "score", "ai_enabled", "is_opted_out", "last_message_at", "created_at")
    list_filter = ("stage", "source", "ai_enabled", "is_opted_out", "organization", "created_at")
    search_fields = ("full_name", "contact_number", "email", "company", "organization__name")
    autocomplete_fields = ("organization", "business_phone", "contact")
    list_select_related = ("organization", "business_phone", "contact")
    readonly_fields = ("handed_over_at", "last_message_at", "last_incoming_at", "last_outgoing_at", "last_ai_reply_at", "opted_out_at", "created_at", "updated_at")
    ordering = ("-last_message_at",)
    date_hierarchy = "created_at"
    list_per_page = 25
    inlines = (LeadActivityInline, LeadTagAssignmentInline)


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "activity_type", "title", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("title", "description", "lead__contact_number")
    autocomplete_fields = ("lead",)
    list_select_related = ("lead",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(LeadTag)
class LeadTagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "lead", "color", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "lead__contact_number")
    autocomplete_fields = ("lead",)
    list_select_related = ("lead",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
    list_per_page = 25


@admin.register(LeadTagAssignment)
class LeadTagAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "tag", "assigned_by_ai", "created_at")
    list_filter = ("assigned_by_ai", "created_at")
    search_fields = ("lead__contact_number", "tag__name")
    autocomplete_fields = ("lead", "tag")
    list_select_related = ("lead", "tag")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25