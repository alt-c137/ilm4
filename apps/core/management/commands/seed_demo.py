"""Демо-контент для дев-окружения: ленты главной живут только с данными.

Запуск: python manage.py seed_demo
Идемпотентно: повторный запуск ничего не задваивает. На прод не запускать.
"""
import io
import math

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from apps.core.models import Moderation
from apps.health.models import Doctor
from apps.maps.models import HalalPlace
from apps.market.models import Category, Listing
from apps.news.models import NewsPost


def make_cover(c1, c2, motif='star'):
    """Красивая обложка 800x500: диагональный градиент + геометрия + блик."""
    size = (800, 500)
    img = Image.new('RGB', size)
    top = tuple(int(a, 16) for a in (c1[0:2], c1[2:4], c1[4:6]))
    bot = tuple(int(a, 16) for a in (c2[0:2], c2[2:4], c2[4:6]))
    px = img.load()
    for y in range(size[1]):
        for x in range(0, size[0], 4):
            t = (x + y) / (size[0] + size[1])
            color = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
            for dx in range(4):
                if x + dx < size[0]:
                    px[x + dx, y] = color
    draw = ImageDraw.Draw(img, 'RGBA')
    # светящиеся круги
    for cx, cy, r in ((650, 90, 130), (120, 420, 160), (420, 250, 90)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 26))
    # восьмиконечная звезда — исламская геометрия
    cx, cy, R = 400, 250, 130
    pts = []
    for i in range(16):
        r = R if i % 2 == 0 else R * 0.42
        a = math.pi * i / 8 - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, outline=(255, 255, 255, 90), width=5)
    draw.regular_polygon((cx, cy, 46), 8, rotation=0, outline=(255, 255, 255, 70), width=3)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = 'Наполнить дев-базу демо-контентом (ленты главной)'

    def handle(self, *args, **options):
        User = get_user_model()
        demo, created = User.objects.get_or_create(
            username='demo',
            defaults={'email': 'demo@ilm4.local', 'first_name': 'Демо'},
        )
        if created:
            demo.set_password('demo-only')
            demo.save()

        # --- новости ---
        news = [
            ('ksa-madina-2027', 'КСА открыла приём иностранных студентов в Университет Медины',
             'Приём документов — до конца месяца, стипендии покрывают учёбу и общежитие.'),
            ('uae-visa-central-asia', 'ОАЭ упростили визы для специалистов из Центральной Азии',
             'Новые категории рабочих виз и ускоренное рассмотрение заявлений.'),
            ('umra-record', 'Число паломников на Умру достигло рекорда',
             'За месяц Умру совершили более 8 миллионов человек — сервисы расширены.'),
            ('halal-expo-tashkent', 'В Ташкенте открылся халяль-фестиваль',
             'Более 200 производителей из 20 стран, вход свободный до воскресенья.'),
        ]
        for slug, title, summary in news:
            NewsPost.objects.get_or_create(slug=slug, defaults={
                'title': title, 'summary': summary, 'body': summary, 'created_by': demo,
            })

        # --- объявления ilmbuy ---
        listings = [
            ('iPhone 14 Pro', 'electronics', 'Ташкент', 720, 'USD', 'Идеал, акуlexer 89%, комплект полный.'),
            ('Ноутбук ASUS VivoBook', 'electronics', 'Ташкент', 540, 'USD', 'Для учёбы и работы, Ryzen 5, 16 ГБ.'),
            ('Молитвенный коврик', 'home', 'Самарканд', 45, 'USD', 'Плотный, с дорожной сумкой.'),
            ('Финики аджва, 1 кг', 'food', 'Бухара', 28, 'USD', 'Свежий урожай, привоз напрямую.'),
            ('Набор книг по акыде', 'books', 'Ташкент', 120000, 'UZS', 'Комплект для начинающих, 4 тома.'),
        ]
        for title, cat_slug, city, price, cur, desc in listings:
            if not Listing.objects.filter(title=title).exists():
                Listing.objects.create(
                    title=title, description=desc, price=price, currency=cur,
                    category=Category.objects.get(slug=cat_slug), city=city,
                    owner=demo, status=Moderation.APPROVED, contact='demo',
                )

        # --- халяль-места ---
        places = [
            ('Кафе Зайнаб', 'cafe', 'Ташкент', 41.311, 69.280, 'Халяль-кухня, семейные залы.'),
            ('Мясная лавка «Халяль»', 'butcher', 'Ташкент', 41.322, 69.290, 'Баранина и говядина с сертификатом.'),
            ('Отель Аль-Фатх', 'hotel', 'Ташкент', 41.300, 69.270, 'Отдельные этажи для семей, намаз-комнаты.'),
        ]
        for name, cat, city, lat, lon, desc in places:
            HalalPlace.objects.get_or_create(name=name, defaults={
                'category': cat, 'city': city, 'lat': lat, 'lon': lon,
                'description': desc, 'status': Moderation.APPROVED, 'owner': demo,
            })

        # --- врачи ---
        doctors = [
            ('Доктор Ахмед Куриев', 'cardio', 'Казань', 'Клиника «Саламат», 12 лет практики.'),
            ('Доктор Марьям Юсупова', 'pediatr', 'Ташкент', 'Педиатр, приём в детской клинике.'),
        ]
        for name, spec, city, desc in doctors:
            Doctor.objects.get_or_create(name=name, defaults={
                'category': spec, 'city': city, 'lat': 41.31, 'lon': 69.28,
                'description': desc, 'status': Moderation.APPROVED, 'owner': demo,
            })

        # --- вопросы форума ---
        from apps.forum.models import Reply, Topic
        topics = [
            ('Можно ли объединять намазы в дороге?', 'Еду Ташкент—Самарканд ночью, удобно ли джам?'),
            ('С чего начать изучение арабского?', 'Хочу читать Коран в оригинале, посоветуйте первые шаги.'),
        ]
        for title, body in topics:
            topic, created = Topic.objects.get_or_create(
                title=title, defaults={'body': body, 'author': demo,
                                       'status': Moderation.APPROVED})
            if created:
                Reply.objects.create(topic=topic, author=demo,
                                     body='Ваалейкум ассалям! Разберём по порядку — смотри подробности в личных…')

        # --- обложки (генерируются локально, без интернета) ---
        covers = {
            'iPhone 14 Pro': ('6d5efc', '3730a3'),
            'Ноутбук ASUS VivoBook': ('0ea5e9', '1e3a8a'),
            'Молитвенный коврик': ('10b981', '065f46'),
            'Финики аджва, 1 кг': ('d97706', '7c2d12'),
            'Набор книг по акыде': ('be123c', '4c0519'),
        }
        for title, (c1, c2) in covers.items():
            listing = Listing.objects.filter(title=title).first()
            if listing and not listing.photo:
                listing.photo.save(f'listing-{title[:20]}.jpg',
                                   make_cover(c1, c2), save=True)

        for i, (slug, _t, _s) in enumerate(news):
            post = NewsPost.objects.filter(slug=slug).first()
            if post and not post.cover:
                palette = [('0e9f5d', '064e3b'), ('2563eb', '1e3a8a'),
                           ('d97706', '7c2d12'), ('db2777', '831843')][i % 4]
                post.cover.save(f'news-{slug[:24]}.jpg',
                                make_cover(*palette), save=True)

        place_colors = [('059669', '064e3b'), ('b45309', '7c2d12'), ('0284c7', '0c4a6e')]
        for j, (name, _c, _ci, _la, _lo, _d) in enumerate(places):
            place = HalalPlace.objects.filter(name=name).first()
            if place and not place.photo:
                place.photo.save(f'place-{j}.jpg',
                                 make_cover(*place_colors[j % 3]), save=True)

        for j, (name, _s, _ci, _d) in enumerate(doctors):
            doctor = Doctor.objects.filter(name=name).first()
            if doctor and not doctor.photo:
                doctor.photo.save(f'doctor-{j}.jpg',
                                  make_cover(*(('8b5cf6', '4c1d95') if j % 2 else ('f43f5e', '881337'))),
                                  save=True)

        self.stdout.write(self.style.SUCCESS(
            f'Демо-данные на месте: новости {NewsPost.objects.count()}, '
            f'объявления {Listing.objects.count()}, места {HalalPlace.objects.count()}, '
            f'врачи {Doctor.objects.count()}'))
