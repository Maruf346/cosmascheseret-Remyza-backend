from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from communications.choices import MessageDirection
from communications.models import Message
from .choices import LeadSource, LeadStage
from .models import Contact, Lead, LeadActivity


HOT_STAGE_VALUES = (LeadStage.HOT,)
WARM_STAGE_VALUES = (LeadStage.WARM, LeadStage.QUALIFIED)
COLD_STAGE_VALUES = (LeadStage.COLD, LeadStage.NEW, LeadStage.CONTACTED)


def time_ago(value):
    if not value:
        return ""
    delta = timezone.now() - value
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "today"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def normalize_contact_number(phone_number, country_code=""):
    value = str(phone_number or "").strip().replace(" ", "").replace("-", "")
    code = str(country_code or "").strip().replace(" ", "")
    if not value:
        return ""
    if value.startswith("+"):
        return value
    if code:
        if not code.startswith("+"):
            code = f"+{code}"
        return f"{code}{value.lstrip('0')}"
    return value


class ContactSerializer(serializers.ModelSerializer):
    is_lead = serializers.SerializerMethodField()
    lead_id = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = (
            "id", "full_name", "country_code", "phone_number", "contact_number", "email",
            "business_name", "notes", "source", "is_lead", "lead_id", "created_at", "updated_at",
        )
        read_only_fields = ("id", "contact_number", "source", "is_lead", "lead_id", "created_at", "updated_at")

    def validate(self, attrs):
        phone_number = attrs.get("phone_number", getattr(self.instance, "phone_number", ""))
        country_code = attrs.get("country_code", getattr(self.instance, "country_code", ""))
        contact_number = normalize_contact_number(phone_number, country_code)
        if not contact_number:
            raise serializers.ValidationError({"phone_number": "Phone number is required."})
        attrs["contact_number"] = contact_number
        return attrs

    @extend_schema_field(bool)
    def get_is_lead(self, obj):
        return bool(obj.linked_lead_id or getattr(obj, "lead_record", None))

    @extend_schema_field(int)
    def get_lead_id(self, obj):
        linked_lead = obj.linked_lead_id or getattr(getattr(obj, "lead_record", None), "id", None)
        return linked_lead


class LeadActivitySerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = ("id", "activity_type", "title", "description", "metadata", "created_at", "time_ago")
        read_only_fields = fields

    @extend_schema_field(str)
    def get_time_ago(self, obj):
        return time_ago(obj.created_at)


class LeadMessageSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id", "conversation", "direction", "sender", "recipient", "message_type", "content",
            "provider_status", "status", "is_ai_generated", "metadata", "created_at", "time_ago",
        )
        read_only_fields = fields

    @extend_schema_field(str)
    def get_time_ago(self, obj):
        return time_ago(obj.created_at)


class LeadSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="company", required=False, allow_blank=True)
    score_percentage = serializers.SerializerMethodField()
    days_in_pipeline = serializers.SerializerMethodField()
    total_messages = serializers.SerializerMethodField()
    inbound_message_count = serializers.SerializerMethodField()
    outbound_message_count = serializers.SerializerMethodField()
    response_rate = serializers.SerializerMethodField()
    last_activity_time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            "id", "contact", "full_name", "contact_number", "email", "business_name", "notes",
            "source", "stage", "score", "score_percentage", "days_in_pipeline",
            "total_messages", "inbound_message_count", "outbound_message_count", "response_rate",
            "ai_enabled", "is_opted_out", "last_message_at", "last_activity_time_ago",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "contact", "full_name", "contact_number", "email", "business_name", "notes", "source",
            "score_percentage", "days_in_pipeline", "total_messages", "inbound_message_count",
            "outbound_message_count", "response_rate", "ai_enabled", "is_opted_out", "last_message_at",
            "last_activity_time_ago", "created_at", "updated_at",
        )

    @extend_schema_field(int)
    def get_score_percentage(self, obj):
        return max(0, min(int(obj.score or 0), 100))

    @extend_schema_field(int)
    def get_days_in_pipeline(self, obj):
        return max((timezone.now().date() - obj.created_at.date()).days, 0)

    @extend_schema_field(int)
    def get_total_messages(self, obj):
        return getattr(obj, "message_total", None) if hasattr(obj, "message_total") else obj.messages.count()

    @extend_schema_field(int)
    def get_inbound_message_count(self, obj):
        return getattr(obj, "inbound_total", None) if hasattr(obj, "inbound_total") else obj.messages.filter(direction=MessageDirection.INBOUND).count()

    @extend_schema_field(int)
    def get_outbound_message_count(self, obj):
        return getattr(obj, "outbound_total", None) if hasattr(obj, "outbound_total") else obj.messages.filter(direction=MessageDirection.OUTBOUND).count()

    @extend_schema_field(int)
    def get_response_rate(self, obj):
        inbound = self.get_inbound_message_count(obj)
        outbound = self.get_outbound_message_count(obj)
        if inbound <= 0:
            return 0
        return min(round((outbound / inbound) * 100), 100)

    @extend_schema_field(str)
    def get_last_activity_time_ago(self, obj):
        return time_ago(obj.last_message_at or obj.updated_at or obj.created_at)


class LeadListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    hot_count = serializers.IntegerField()
    warm_count = serializers.IntegerField()
    cold_count = serializers.IntegerField()
    results = LeadSerializer(many=True)


class LeadInboxSerializer(LeadSerializer):
    last_message = serializers.SerializerMethodField()
    unread_messages = serializers.SerializerMethodField()

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + ("last_message", "unread_messages")
        read_only_fields = LeadSerializer.Meta.read_only_fields + ("last_message", "unread_messages")

    @extend_schema_field(LeadMessageSerializer)
    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if not message:
            return None
        return LeadMessageSerializer(message).data

    @extend_schema_field(int)
    def get_unread_messages(self, obj):
        return getattr(obj, "unread_total", None) or 0


class LeadDetailSerializer(LeadSerializer):
    activities = LeadActivitySerializer(many=True, read_only=True)
    conversation = serializers.SerializerMethodField()

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + ("summary", "metadata", "activities", "conversation")
        read_only_fields = LeadSerializer.Meta.read_only_fields + ("summary", "metadata", "activities", "conversation")

    @extend_schema_field(LeadMessageSerializer(many=True))
    def get_conversation(self, obj):
        messages = obj.messages.select_related("conversation").order_by("created_at")
        return LeadMessageSerializer(messages, many=True).data


class ContactCSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ContactCSVUploadResponseSerializer(serializers.Serializer):
    created_count = serializers.IntegerField()
    duplicate_count = serializers.IntegerField()
    error_count = serializers.IntegerField()
    duplicates = serializers.ListField(child=serializers.DictField())
    errors = serializers.ListField(child=serializers.DictField())
    created = serializers.ListField(child=serializers.DictField())


class LeadStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    hot = serializers.IntegerField()
    warm = serializers.IntegerField()
    cold = serializers.IntegerField()
    opted_out = serializers.IntegerField()
