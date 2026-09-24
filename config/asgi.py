"""ASGI: HTTP + WebSocket (чат, фаза 8).

Запуск в деве: channels runserver (как manage.py runserver, ASGI-версия).
Прод: daphne/uvicorn — в фазе деплоя (docker-compose.prod).
"""
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

from apps.api.ws import TokenOrSession
from apps.chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    # сайт — сессия + проверка Origin; приложение — токен в заголовке (apps/api/ws.py)
    'websocket': TokenOrSession(URLRouter(websocket_urlpatterns)),
})
