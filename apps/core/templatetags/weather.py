"""Тег погоды для инфопанели главной: {% get_weather as wx %}.

Open-Meteo (бесплатный, без ключа), кеш в памяти процесса на 30 минут.
При недоступности сервиса возвращает None — панель просто без погоды.
"""
import json
import time
import urllib.request

from django import template

register = template.Library()

_CACHE = {"ts": 0.0, "data": None}
_TTL = 1800  # секунд
_TASHKENT = ("https://api.open-meteo.com/v1/forecast"
             "?latitude=41.3111&longitude=69.2797"
             "&current=temperature_2m,weather_code"
             "&daily=temperature_2m_max,temperature_2m_min"
             "&timezone=auto&forecast_days=1")

_CODE_DESC = {
    0: "Ясно", 1: "Малооблачно", 2: "Облачно", 3: "Пасмурно",
    45: "Туман", 48: "Туман",
    51: "Морось", 53: "Морось", 55: "Морось", 56: "Морось", 57: "Морось",
    61: "Дождь", 63: "Дождь", 65: "Ливень", 66: "Дождь", 67: "Ливень",
    71: "Снег", 73: "Снег", 75: "Снег", 77: "Снег",
    80: "Ливень", 81: "Ливень", 82: "Ливень", 85: "Снег", 86: "Снег",
    95: "Гроза", 96: "Гроза", 99: "Гроза",
}
_DESC_KIND = {
    "Ясно": "sun", "Малооблачно": "partly", "Облачно": "partly", "Пасмурно": "cloud",
    "Туман": "fog", "Морось": "rain", "Дождь": "rain", "Ливень": "rain",
    "Снег": "snow", "Гроза": "storm",
}


@register.simple_tag
def get_weather():
    now = time.time()
    if _CACHE["data"] is not None and now - _CACHE["ts"] < _TTL:
        return _CACHE["data"]
    data = None
    try:
        req = urllib.request.Request(_TASHKENT, headers={"User-Agent": "ilm4/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode())
        code = payload["current"]["weather_code"]
        desc = _CODE_DESC.get(code, "")
        data = {
            "temp": round(payload["current"]["temperature_2m"]),
            "desc": desc,
            "kind": _DESC_KIND.get(desc, "cloud"),
            "tmax": round(payload["daily"]["temperature_2m_max"][0]),
            "tmin": round(payload["daily"]["temperature_2m_min"][0]),
        }
    except Exception:
        data = None
    if data is not None:
        _CACHE["ts"] = now
        _CACHE["data"] = data
    return data
