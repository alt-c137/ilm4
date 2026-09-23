"""Перезаписать демо-обложки мягкими градиентами (без узоров).

Запуск: python manage.py refresh_covers
Не создаёт и не удаляет объекты — только перерисовывает картинки.
"""
from django.core.management.base import BaseCommand

from apps.core.management.commands.seed_demo import make_cover
from apps.health.models import Doctor
from apps.maps.models import HalalPlace
from apps.market.models import Listing
from apps.news.models import NewsPost

PALETTES = [
    ('6d5efc', '8b7dff'),
    ('12b268', '3ecf8e'),
    ('0ea5c4', '4dd0e1'),
    ('f59e0b', 'fbbf24'),
    ('ec4899', 'f472b6'),
]


class Command(BaseCommand):
    help = 'Перерисовать демо-обложки мягкими пастельными градиентами'

    def handle(self, *args, **options):
        n = 0
        for i, l in enumerate(Listing.objects.exclude(photo='')):
            l.photo.save(l.photo.name, make_cover(*PALETTES[i % len(PALETTES)]), save=True)
            n += 1
        for i, p in enumerate(NewsPost.objects.exclude(cover='')):
            p.cover.save(p.cover.name, make_cover(*PALETTES[(i + 2) % len(PALETTES)]), save=True)
            n += 1
        for i, p in enumerate(HalalPlace.objects.exclude(photo='')):
            p.photo.save(p.photo.name, make_cover(*PALETTES[(i + 1) % len(PALETTES)]), save=True)
            n += 1
        for i, d in enumerate(Doctor.objects.exclude(photo='')):
            d.photo.save(d.photo.name, make_cover(*PALETTES[(i + 4) % len(PALETTES)]), save=True)
            n += 1
        self.stdout.write(self.style.SUCCESS(f'Обновлено обложек: {n}'))
