"""Вебхук бота (сервер): Telegram присылает сюда обновления. На ПК вместо него — manage.py tg_bot."""
import hmac
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .dispatch import handle_update


@csrf_exempt   # доказательство — секрет вебхука в заголовке, а не CSRF-токен
@require_POST
def webhook(request):
    secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
    got = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not secret or not hmac.compare_digest(secret, got):
        return HttpResponseForbidden()
    try:
        update = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    handle_update(update)
    return HttpResponse('ok')
