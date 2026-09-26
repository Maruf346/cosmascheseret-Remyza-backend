import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone


class NotificationConsumer(AsyncWebsocketConsumer):
    """Admin-only websocket consumer for live notification delivery."""

    async def connect(self):
        token = self._extract_token()
        self.user = await self.get_user_from_token(token)

        if not await self.is_allowed_admin(self.user):
            await self.close(code=4003)
            return

        self.group_name = f"admin_notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to admin notification service.",
            "unread_count": await self.get_unread_count(),
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action")
        if action == "mark_read" and data.get("notification_id"):
            await self.mark_notification_read(data["notification_id"])
            await self.send(text_data=json.dumps({"type": "unread_count", "count": await self.get_unread_count()}))
        elif action == "mark_all_read":
            await self.mark_all_read()
            await self.send(text_data=json.dumps({"type": "unread_count", "count": 0}))

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification_id": event.get("notification_id"),
            "notification_type": event.get("notification_type"),
            "title": event.get("title"),
            "body": event.get("body"),
            "data": event.get("data", {}),
            "priority": event.get("priority", "normal"),
            "created_at": event.get("created_at"),
            "unread_count": event.get("unread_count"),
        }))

    def _extract_token(self):
        query = self.scope.get("query_string", b"").decode()
        return parse_qs(query).get("token", [""])[0]

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return AnonymousUser()
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except Exception:
            return AnonymousUser()

    @database_sync_to_async
    def is_allowed_admin(self, user):
        if not user or isinstance(user, AnonymousUser):
            return False
        from accounts.choices import UserType

        return bool(user.is_staff or user.is_superuser or getattr(user, "user_type", None) == UserType.ADMIN)

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from .models import Notification

        try:
            notification = Notification.objects.get(id=notification_id, user=self.user)
            notification.mark_read()
        except Notification.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_all_read(self):
        from .models import Notification

        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True, read_at=timezone.now())

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification

        return Notification.objects.filter(user=self.user, is_read=False).count()