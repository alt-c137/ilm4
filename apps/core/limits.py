"""Счётчики для ограничений частоты (флуд, спам, перебор).

Считаем одной операцией в кеше (в проде это Redis — общий на все процессы и серверы). Запись «прочитал — прибавил —
записал» двумя шагами не годится: два запроса в один момент прочитают одно и то же число и оба пройдут."""
from django.core.cache import cache


def hits(key: str, window: int) -> int:
    """Отметить ещё одно действие и вернуть, сколько их за окно (секунды)."""
    cache.add(key, 0, window)
    try:
        return cache.incr(key)
    except ValueError:                 # ключ истёк между add и incr
        cache.set(key, 1, window)
        return 1


LOCAL = ('127.0.0.1', '::1', 'localhost')


def client_ip(request) -> str:
    """Настоящий адрес посетителя — по нему считаются лимиты входа, регистраций и запросов.

    Заголовкам верим не всем подряд (их легко подделать), а только от того, кто действительно стоит перед сайтом:
    * сервер (prod): перед приложением nginx, он кладёт проверенный адрес в X-Real-IP — CLIENT_IP_HEADER в настройках;
    * свой ПК с туннелем (scripts/run_local.sh): запрос приходит от туннеля на этом же компьютере (127.0.0.1) —
      тогда берём адрес, который сообщил туннель; без этого все посетители выглядели бы одним адресом
      и делили бы одни лимиты на всех;
    * иначе — адрес самого соединения."""
    from django.conf import settings
    meta = getattr(request, 'META', None) or {}
    header = getattr(settings, 'CLIENT_IP_HEADER', '')
    addr = (meta.get('REMOTE_ADDR') or '').strip()
    if header:
        return (meta.get(header) or addr).strip()[:45]
    if addr in LOCAL:
        via = (meta.get('HTTP_CF_CONNECTING_IP') or meta.get('HTTP_X_FORWARDED_FOR', '').split(',')[-1]).strip()
        return (via or addr)[:45]
    return addr[:45]
