"""Поставщики ИИ для помощника. Два вида API:

* 'anthropic' — Claude через официальный SDK (apps/assistant/services.py, _step_anthropic);
* 'openai'    — любой сервис с OpenAI-совместимым «chat/completions»: OpenAI, Z.AI (GLM), OpenRouter, DeepSeek, Groq…

Адрес сервера человек сам ввести не может — только выбрать из списка: иначе сайт можно было бы заставить ходить
по внутренним адресам (SSRF). Свой сервер добавляет владелец площадки: ASSISTANT_EXTRA_HOSTS в .env.

Подписки Claude Pro / ChatGPT Plus сюда подключить нельзя — они не выдают ключ для чужих программ. Подходят сервисы,
которые дают ключ: API Anthropic / OpenAI (оплата по факту), Z.AI (в т.ч. подписка Coding Plan — ключ есть), OpenRouter.
"""
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy

PRESETS = {
    'anthropic': {'name': 'Claude (Anthropic)', 'api': 'anthropic', 'base': '', 'model': 'claude-opus-5-5',
                  'where': 'console.anthropic.com', 'prefix': 'sk-ant-'},
    'openai': {'name': 'OpenAI', 'api': 'openai', 'base': 'https://api.openai.com/v1', 'model': 'gpt-6.1-sol',
               'where': 'platform.openai.com', 'prefix': 'sk-'},
    'zai': {'name': 'Z.AI (GLM) — API', 'api': 'openai', 'base': 'https://api.z.ai/api/paas/v4', 'model': 'glm-5.3',
            'where': 'z.ai', 'prefix': ''},
    'zai_coding': {'name': _lazy('Z.AI — подписка Coding Plan'), 'api': 'openai', 'base': 'https://api.z.ai/api/coding/paas/v4',
                   'model': 'glm-5.3', 'where': 'z.ai', 'prefix': ''},
    'openrouter': {'name': 'OpenRouter', 'api': 'openai', 'base': 'https://openrouter.ai/api/v1', 'model': 'openrouter/auto',
                   'where': 'openrouter.ai', 'prefix': 'sk-or-'},
    'deepseek': {'name': 'DeepSeek', 'api': 'openai', 'base': 'https://api.deepseek.com/v1', 'model': 'deepseek-chat',
                 'where': 'platform.deepseek.com', 'prefix': 'sk-'},
    'custom': {'name': _lazy('Свой сервер (разрешает владелец площадки)'), 'api': 'openai', 'base': '', 'model': '',
               'where': '', 'prefix': ''},
}
MODEL_RE = re.compile(r'^[\w.\-:/@]{1,80}$')


class ProviderError(Exception):
    pass


def choices() -> list:
    return [{'key': k, 'name': str(v['name']), 'model': v['model'], 'where': v['where'], 'custom': k == 'custom'}
            for k, v in PRESETS.items() if k != 'custom' or extra_hosts()]


def extra_hosts() -> list:
    return [h.strip().lower() for h in getattr(settings, 'ASSISTANT_EXTRA_HOSTS', []) if h.strip()]


def clean(provider: str, model: str = '', base_url: str = '') -> dict:
    """Проверить выбор человека. Возвращает {'provider','model','base_url'} или бросает ProviderError."""
    preset = PRESETS.get(provider)
    if preset is None:
        raise ProviderError('provider')
    model = (model or '').strip()
    if model and not MODEL_RE.match(model):
        raise ProviderError('model')
    base = ''
    if provider == 'custom':
        base = (base_url or '').strip().rstrip('/')
        parts = urlsplit(base)
        if parts.scheme != 'https' or (parts.hostname or '').lower() not in extra_hosts():
            raise ProviderError('base_url')
        if not model:
            raise ProviderError('model')
    return {'provider': provider, 'model': model, 'base_url': base}


def resolve(provider: str, model: str = '', base_url: str = '') -> dict:
    """Готовая настройка для запроса: {'provider','api','base','model'}."""
    preset = PRESETS.get(provider) or PRESETS['anthropic']
    return {'provider': provider if provider in PRESETS else 'anthropic', 'api': preset['api'],
            'base': (base_url if provider == 'custom' else preset['base']).rstrip('/'), 'model': model or preset['model']}


def site() -> dict | None:
    """ИИ площадки (.env): ASSISTANT_API_KEY + ASSISTANT_PROVIDER [+ ASSISTANT_MODEL] — или, по-старому, ANTHROPIC_API_KEY."""
    key = getattr(settings, 'ASSISTANT_API_KEY', '')
    if key:
        cfg = resolve(getattr(settings, 'ASSISTANT_PROVIDER', 'openai') or 'openai', getattr(settings, 'ASSISTANT_MODEL', ''),
                      getattr(settings, 'ASSISTANT_BASE_URL', ''))
        return {**cfg, 'key': key}
    key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if key:
        return {**resolve('anthropic', getattr(settings, 'ASSISTANT_MODEL', '')), 'key': key}
    return None
