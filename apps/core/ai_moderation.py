"""ИИ-модератор: проверяет новые публикации и анкеты до того, как их увидит человек-модератор.

Как работает:
  1. Сервис jobs раз в минуту запускает `manage.py ai_moderate`.
  2. Всё, что «на проверке» и ещё не проверялось ИИ (или изменилось), уходит в модель.
  3. Вердикт ok / review / reject + причины сохраняются (админка → Проверки ИИ) и
     уходят сводкой в Telegram-группу модераторов.
  4. Если в настройках включено «ИИ одобряет сам» — «ok» публикуется без человека.

Провайдеры (ключ в .env):
  ANTHROPIC_API_KEY — Claude (понимает контекст: харам, мошенничество, контакты, возраст) — основной;
  OPENAI_API_KEY    — бесплатный OpenAI moderation (только грубые категории: 18+, насилие, ненависть).
Без ключей работает только бесплатная проверка контактов (телефоны, ники, ссылки).
"""
import base64
import hashlib
import json
import logging
import re

import requests
from django.conf import settings

log = logging.getLogger(__name__)

RULES = """Ты модератор ilm4 — платформы мусульманского сообщества (СНГ и мир): объявления купли-продажи,
вакансии и резюме, услуги и фриланс, перевозки, места на халяль-карте, врачи, форум, истории переезда
и анкеты никяха (знакомство для брака по шариату).

Отметь нарушения:
- контакты в анкете никяха: телефоны, ники (@…), ссылки, названия мессенджеров для связи (в объявлениях и
  вакансиях контакты разрешены);
- неприличное, сексуальное, флирт или «общение ради общения» в никяхе;
- харам-товары и услуги: алкоголь, свинина, азартные игры, ростовщичество (риба), колдовство, наркотики;
- признаки мошенничества: предоплата незнакомцу, «гарантированный доход», пирамиды, слишком низкие цены;
- оскорбления, ненависть, угрозы, экстремизм, призывы к насилию;
- спам, бессмысленный текст, реклама посторонних сервисов;
- возраст младше 18 лет в никяхе.

Ответь СТРОГО одним JSON без пояснений:
{"verdict": "ok" | "review" | "reject", "reasons": ["коротко по-русски, что не так"]}
ok — нарушений нет; review — сомнительно, пусть решит человек; reject — явное нарушение."""

VERDICTS = {'ok', 'review', 'reject'}


def enabled() -> bool:
    from .models import SiteSettings
    return SiteSettings.get_solo().ai_moderation_enabled and bool(
        getattr(settings, 'ANTHROPIC_API_KEY', '') or getattr(settings, 'OPENAI_API_KEY', ''))


def content_hash(text: str, extra: bytes = b'') -> str:
    return hashlib.sha256(text.encode() + extra).hexdigest()


def _claude(text: str, image: bytes | None = None) -> dict:
    content = [{'type': 'text', 'text': text[:12000]}]
    if image:
        content.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                                       'data': base64.b64encode(image).decode()}})
        content.append({'type': 'text', 'text': 'Проверь и фото анкеты: один человек, прилично одет, без текста '
                                                 'и контактов на фото, не чужое/не из интернета.'})
    r = requests.post('https://api.anthropic.com/v1/messages', timeout=40, headers={
        'x-api-key': settings.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json',
    }, json={'model': settings.AI_MODERATION_MODEL, 'max_tokens': 400, 'system': RULES,
             'messages': [{'role': 'user', 'content': content}]})
    r.raise_for_status()
    answer = ''.join(b.get('text', '') for b in r.json().get('content', []))
    m = re.search(r'\{.*\}', answer, re.DOTALL)
    data = json.loads(m.group(0)) if m else {}
    verdict = data.get('verdict') if data.get('verdict') in VERDICTS else 'review'
    return {'verdict': verdict, 'reasons': [str(x)[:200] for x in data.get('reasons', [])][:6],
            'model': settings.AI_MODERATION_MODEL}


def _openai(text: str, image: bytes | None = None) -> dict:
    inputs = [{'type': 'text', 'text': text[:12000]}]
    if image:
        inputs.append({'type': 'image_url',
                       'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}})
    r = requests.post('https://api.openai.com/v1/moderations', timeout=30,
                      headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'},
                      json={'model': 'omni-moderation-latest', 'input': inputs})
    r.raise_for_status()
    res = r.json()['results'][0]
    cats = [k for k, v in res.get('categories', {}).items() if v]
    return {'verdict': 'review' if res.get('flagged') else 'ok', 'reasons': cats, 'model': 'omni-moderation-latest'}


def check(text: str, image: bytes | None = None, contacts_forbidden: bool = False) -> dict:
    """Проверить текст (и фото). Бесплатная проверка контактов — всегда первой."""
    if contacts_forbidden:
        from apps.nikah.services import has_contacts
        if has_contacts(text):
            return {'verdict': 'reject', 'reasons': ['Контакты в анкете (телефон, ник, ссылка)'], 'model': 'regex'}
    try:
        if getattr(settings, 'ANTHROPIC_API_KEY', ''):
            return _claude(text, image)
        if getattr(settings, 'OPENAI_API_KEY', ''):
            return _openai(text, image)
    except (requests.RequestException, ValueError, KeyError) as exc:
        log.warning('ИИ-модерация: ошибка провайдера: %s', exc)
        return {'verdict': 'error', 'reasons': [str(exc)[:200]], 'model': ''}
    return {'verdict': 'ok', 'reasons': [], 'model': 'regex'}
