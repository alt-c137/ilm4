"""Проверка «сайт жив» для Docker (docker-compose.prod.yml → healthcheck).

Стучится в /healthz/ изнутри контейнера так, как это делает nginx: с настоящим именем сайта
и пометкой https — иначе Django ответил бы «чужой адрес» или отправил на https.
"""
import os
import sys
import urllib.request

host = (os.environ.get('ALLOWED_HOSTS', '') or 'localhost').split(',')[0].strip().lstrip('.')
if host in ('', '*'):
    host = 'localhost'
port = os.environ.get('HEALTH_PORT', '8000')
req = urllib.request.Request(f'http://127.0.0.1:{port}/healthz/', headers={'Host': host, 'X-Forwarded-Proto': 'https'})
try:
    ok = urllib.request.urlopen(req, timeout=4).status == 200
except Exception:                                                 # noqa: BLE001
    ok = False
sys.exit(0 if ok else 1)
