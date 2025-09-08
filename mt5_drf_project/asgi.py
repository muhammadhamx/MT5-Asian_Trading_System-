"""
ASGI config for mt5_drf_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# import os

# from django.core.asgi import get_asgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mt5_drf_project.settings')

# application = get_asgi_application()

# asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from mt5_integration import routing
from .middleware import HTTPSRedirectMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mt5_drf_project.settings')

application = ProtocolTypeRouter({
    "http": HTTPSRedirectMiddleware(get_asgi_application()),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})