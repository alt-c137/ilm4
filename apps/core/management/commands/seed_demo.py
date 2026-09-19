"""Демо-контент для дев-окружения: ленты главной живут только с данными.

Запуск: python manage.py seed_demo
Идемпотентно: повторный запуск ничего не задваивает. На прод не запускать.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.models import Moderation
from apps.health.models import Doctor
from apps.maps.models import HalalPlace
from apps.market.models import Category, Listing
from apps.news.models import NewsPost


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

        self.stdout.write(self.style.SUCCESS(
            f'Демо-данные на месте: новости {NewsPost.objects.count()}, '
            f'объявления {Listing.objects.count()}, места {HalalPlace.objects.count()}, '
            f'врачи {Doctor.objects.count()}'))
