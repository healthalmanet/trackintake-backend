import os
from django.core.asgi import get_asgi_application
from dotenv import load_dotenv
from channels.routing import ProtocolTypeRouter, URLRouter
import django
load_dotenv() 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from middlewares.webSocket import TokenAuthMiddleware
from features.urls import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": TokenAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
