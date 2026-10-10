from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "title",
            "body",
            "data",
            "priority",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NotificationUnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


class NotificationPaginatedResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = NotificationSerializer(many=True)


class NotificationMarkAllReadResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    updated_count = serializers.IntegerField()


class NotificationClearReadResponseSerializer(serializers.Serializer):
    deleted_count = serializers.IntegerField()
