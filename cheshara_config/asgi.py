"""
ASGI config for cheshara_config project.

HTTP is served by Django's ASGI application. Admin notification websockets are
served through Channels at /ws/admin/notifications/?token=<jwt>.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cheshara_config.settings")

django_asgi_app = get_asgi_application()

from notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)