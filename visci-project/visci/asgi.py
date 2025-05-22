import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'visci.settings')

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import visci.routing  # where your WebSocket routing lives

from django.core.asgi import get_asgi_application

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # still handles normal HTTP requests
    "websocket": AuthMiddlewareStack(
        URLRouter(
            visci.routing.websocket_urlpatterns
        )
    ),
})