"""Обновить курсы валют к суму: python manage.py pull_rates

Источник: open.er-api.com (без ключа). Курсы хранятся в БД — главная
показывает последние сохранённые, даже если сеть временно недоступна.
На проде запускать раз в сутки (cron/Celery).
"""
import json
import urllib.request

from django.core.management.base import BaseCommand

from apps.core.models import Rate

API = 'https://open.er-api.com/v6/latest/USD'
CODES = ['USD', 'EUR', 'RUB']  # к суму (UZS)


class Command(BaseCommand):
    help = 'Обновить курсы валют (USD/EUR/RUB к UZS)'

    def handle(self, *args, **options):
        with urllib.request.urlopen(API, timeout=15) as response:
            data = json.loads(response.read().decode())
        if data.get('result') != 'success':
            raise SystemExit('API вернуло ошибку: ' + str(data)[:200])
        per_usd = data['rates']  # сколько валюты за 1 USD
        for code in CODES:
            if code == 'USD':
                rate_uzs = per_usd['UZS']
            else:
                rate_uzs = per_usd['UZS'] / per_usd[code]
            Rate.objects.update_or_create(
                code=code, defaults={'rate': round(rate_uzs, 2)})
            self.stdout.write(f'{code}: {rate_uzs:.2f} сум')
        self.stdout.write(self.style.SUCCESS('Курсы обновлены'))
