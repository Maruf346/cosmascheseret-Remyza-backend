import csv
import io

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from communications.choices import MessageDirection
from .choices import LeadActivityType, LeadSource, LeadStage
from .models import Contact, Lead, LeadActivity
from .serializers import (
    COLD_STAGE_VALUES,
    HOT_STAGE_VALUES,
    WARM_STAGE_VALUES,
    ContactCSVUploadResponseSerializer,
    ContactCSVUploadSerializer,
    ContactSerializer,
    LeadDetailSerializer,
    LeadInboxSerializer,
    LeadListResponseSerializer,
    LeadMessageSerializer,
    LeadSerializer,
    LeadStatsSerializer,
    normalize_contact_number,
)


STAGE_GROUPS = {
    "hot": HOT_STAGE_VALUES,
    "warm": WARM_STAGE_VALUES,
    "cold": COLD_STAGE_VALUES,
}


class LeadPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ContactPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def get_contact_value(row, *keys):
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""




def enqueue_contact_welcome_message(contact):
    # Automatic welcome-message sending is intentionally disabled.
    # Keeping the previous implementation below as reference only because fully dynamic/automatic
    # first-touch messages can create SMS/10DLC and WhatsApp compliance risk.
    return
    # settings_obj = getattr(contact.organization, "settings", None)
    # if not settings_obj or not getattr(settings_obj, "auto_welcome_message_enabled", False):
    #     return
    # try:
    #     from sentdm.tasks import send_contact_welcome_message_task
    #     transaction.on_commit(lambda: send_contact_welcome_message_task.delay(contact.id))
    # except Exception:
    #     return


def create_activity(lead, activity_type, title, description="", metadata=None):
    return LeadActivity.objects.create(
        lead=lead,
        activity_type=activity_type,
        title=title,
        description=description,
        metadata=metadata or {},
    )


class OrganizationScopedMixin:
    def get_organization(self):
        user = self.request.user
        return getattr(user, "organization", None)

    def get_organization_or_raise(self):
        organization = self.get_organization()
        if not organization:
            raise ValidationError({"organization": "Create your business profile before using CRM."})
        return organization


@extend_schema(tags=["CRM - Contacts"])
class ContactViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContactPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return Contact.objects.none()
        organization = self.get_organization()
        if not organization:
            return Contact.objects.none()
        queryset = Contact.objects.filter(organization=organization).select_related("linked_lead")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(contact_number__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(email__icontains=search)
                | Q(business_name__icontains=search)
            )
        return queryset

    @extend_schema(
        summary="List contacts",
        description="Returns saved address-book contacts. These are not leads until the contact enters the messaging/pipeline flow.",
        parameters=[OpenApiParameter("search", str, required=False, description="Search by name, phone, email, or business name.")],
        responses={200: ContactSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create contact",
        description="Saves a contact with full name, country code, phone number, email, business name, and notes.",
        request=ContactSerializer,
        responses={201: ContactSerializer, 400: OpenApiResponse(description="Missing business profile, duplicate contact, or invalid contact data.")},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        organization = self.get_organization_or_raise()
        try:
            contact = serializer.save(organization=organization, source=LeadSource.MANUAL)
            enqueue_contact_welcome_message(contact)
        except IntegrityError:
            raise ValidationError({"phone_number": "This contact already exists."})

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({"phone_number": "This contact already exists."})

    @extend_schema(
        summary="Upload contacts CSV",
        description="Creates saved contacts from a CSV file and returns duplicate rows separately. Supported columns include full_name/name, phone_number/contact_number/phone, country_code, email, business_name/company, and notes.",
        request=ContactCSVUploadSerializer,
        responses={200: ContactCSVUploadResponseSerializer, 400: OpenApiResponse(description="Invalid or unreadable CSV file.")},
    )
    @action(detail=False, methods=["post"], url_path="upload-csv", parser_classes=[MultiPartParser, FormParser])
    def upload_csv(self, request):
        organization = self.get_organization_or_raise()
        serializer = ContactCSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]

        try:
            decoded = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError({"file": "Upload a valid UTF-8 CSV file."})

        reader = csv.DictReader(io.StringIO(decoded))
        if not reader.fieldnames:
            raise ValidationError({"file": "CSV file must include a header row."})

        created = []
        duplicates = []
        errors = []
        seen_numbers = set()

        for row_number, row in enumerate(reader, start=2):
            raw_phone = get_contact_value(row, "phone_number", "contact_number", "phone", "mobile", "number")
            country_code = get_contact_value(row, "country_code", "country code", "dial_code")
            contact_number = normalize_contact_number(raw_phone, country_code)
            full_name = get_contact_value(row, "full_name", "name", "contact_name")
            email = get_contact_value(row, "email", "email_address")
            business_name = get_contact_value(row, "business_name", "company", "company_name")
            notes = get_contact_value(row, "notes", "note")

            if not contact_number:
                errors.append({"row": row_number, "reason": "phone_number is required."})
                continue

            duplicate_payload = {
                "row": row_number,
                "full_name": full_name,
                "country_code": country_code,
                "phone_number": raw_phone,
                "contact_number": contact_number,
                "email": email,
                "business_name": business_name,
            }
            if contact_number in seen_numbers:
                duplicates.append({**duplicate_payload, "reason": "Duplicate in uploaded CSV."})
                continue
            seen_numbers.add(contact_number)

            if Contact.objects.filter(organization=organization, contact_number=contact_number).exists():
                duplicates.append({**duplicate_payload, "reason": "Contact already exists."})
                continue

            try:
                contact = Contact.objects.create(
                    organization=organization,
                    full_name=full_name,
                    country_code=country_code,
                    phone_number=raw_phone,
                    contact_number=contact_number,
                    email=email,
                    business_name=business_name,
                    notes=notes,
                    source=LeadSource.CSV_UPLOAD,
                )
                created.append({"id": contact.id, "full_name": contact.full_name, "contact_number": contact.contact_number})
                enqueue_contact_welcome_message(contact)
            except IntegrityError:
                duplicates.append({**duplicate_payload, "reason": "Contact already exists."})

        return Response(
            {
                "created_count": len(created),
                "duplicate_count": len(duplicates),
                "error_count": len(errors),
                "duplicates": duplicates,
                "errors": errors,
                "created": created,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["CRM - Leads"])
class LeadViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LeadDetailSerializer
        if self.action == "inbox":
            return LeadInboxSerializer
        return LeadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return Lead.objects.none()
        organization = self.get_organization()
        if not organization:
            return Lead.objects.none()

        queryset = (
            Lead.objects.filter(organization=organization)
            .select_related("contact")
            .annotate(
                message_total=Count("messages", distinct=True),
                inbound_total=Count("messages", filter=Q(messages__direction=MessageDirection.INBOUND), distinct=True),
                outbound_total=Count("messages", filter=Q(messages__direction=MessageDirection.OUTBOUND), distinct=True),
            )
            .prefetch_related("activities")
            .order_by("-last_message_at", "-created_at")
        )

        return self.apply_filters(queryset)

    def apply_filters(self, queryset, include_stage=True):
        if include_stage:
            stage = (self.request.query_params.get("stage") or "").strip().lower()
            if stage in STAGE_GROUPS:
                queryset = queryset.filter(stage__in=STAGE_GROUPS[stage])
            elif stage:
                queryset = queryset.filter(stage=stage)

        source = (self.request.query_params.get("source") or "").strip().lower()
        if source:
            queryset = queryset.filter(source=source)

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(contact_number__icontains=search)
                | Q(email__icontains=search)
                | Q(company__icontains=search)
                | Q(contact__business_name__icontains=search)
            )
        return queryset

    def get_stage_counts(self):
        organization = self.get_organization()
        if not organization:
            return {"hot_count": 0, "warm_count": 0, "cold_count": 0}
        queryset = self.apply_filters(Lead.objects.filter(organization=organization), include_stage=False)
        return {
            "hot_count": queryset.filter(stage__in=HOT_STAGE_VALUES).count(),
            "warm_count": queryset.filter(stage__in=WARM_STAGE_VALUES).count(),
            "cold_count": queryset.filter(stage__in=COLD_STAGE_VALUES).count(),
        }

    @extend_schema(
        summary="List leads",
        description="Returns paginated pipeline leads. A lead is created when a contact/person engages through messaging or is otherwise promoted into the pipeline.",
        parameters=[
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
            OpenApiParameter("stage", str, required=False, description="Filter by lead stage group: hot, warm, cold, or a stored stage value."),
            OpenApiParameter("source", str, required=False, description="Filter by source: auto_capture, sentdm, manual, or csv_upload."),
            OpenApiParameter("search", str, required=False, description="Search by name, phone, email, or business name."),
        ],
        responses={200: LeadListResponseSerializer},
    )
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict):
            response.data.update(self.get_stage_counts())
        return response

    @extend_schema(
        summary="Get lead details",
        description="Returns lead details, metrics, activities, and message conversation.",
        responses={200: LeadDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update lead status",
        description="Updates lead pipeline fields such as stage. If stage changes, a lead activity is recorded automatically.",
        request=LeadSerializer,
        responses={200: LeadSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_update(self, serializer):
        old_stage = serializer.instance.stage
        lead = serializer.save()
        if old_stage != lead.stage:
            create_activity(
                lead,
                LeadActivityType.STAGE_CHANGED,
                f"Status changed to {lead.get_stage_display()}",
                f"Lead status changed from {old_stage} to {lead.stage}.",
                {"from": old_stage, "to": lead.stage},
            )

    @extend_schema(
        summary="List lead inbox",
        description="Returns one row per lead that has conversation messages, including lead details, latest message, unread count, and lead metrics.",
        parameters=[
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
            OpenApiParameter("stage", str, required=False, description="Filter by lead stage group: hot, warm, cold, or a stored stage value."),
            OpenApiParameter("source", str, required=False, description="Filter by source: auto_capture, sentdm, manual, or csv_upload."),
            OpenApiParameter("search", str, required=False, description="Search by name, phone, email, or business name."),
        ],
        responses={200: LeadInboxSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="inbox")
    def inbox(self, request):
        organization = self.get_organization_or_raise()
        queryset = (
            Lead.objects.filter(organization=organization, messages__isnull=False)
            .select_related("contact")
            .annotate(
                message_total=Count("messages", distinct=True),
                inbound_total=Count("messages", filter=Q(messages__direction=MessageDirection.INBOUND), distinct=True),
                outbound_total=Count("messages", filter=Q(messages__direction=MessageDirection.OUTBOUND), distinct=True),
                unread_total=Sum("conversations__unread_messages", distinct=True),
            )
            .distinct()
            .order_by("-last_message_at", "-created_at")
        )
        queryset = self.apply_filters(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = LeadInboxSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = LeadInboxSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="List lead conversation messages",
        description="Returns the full message history for one lead with pagination. Use this for the conversation screen instead of relying on the compact lead detail response.",
        parameters=[
            OpenApiParameter("page", int, required=False, description="Page number."),
            OpenApiParameter("page_size", int, required=False, description="Items per page, up to 100."),
        ],
        responses={200: LeadMessageSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="conversation")
    def conversation(self, request, pk=None):
        lead = self.get_object()
        queryset = lead.messages.select_related("conversation").order_by("created_at")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = LeadMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = LeadMessageSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get lead counts",
        description="Returns total, hot, warm, cold, and opted-out lead counts for the authenticated user's organization.",
        responses={200: LeadStatsSerializer},
    )
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        queryset = self.get_queryset()
        return Response(
            {
                "total": queryset.count(),
                "hot": queryset.filter(stage__in=HOT_STAGE_VALUES).count(),
                "warm": queryset.filter(stage__in=WARM_STAGE_VALUES).count(),
                "cold": queryset.filter(stage__in=COLD_STAGE_VALUES).count(),
                "opted_out": queryset.filter(is_opted_out=True).count(),
            }
        )
