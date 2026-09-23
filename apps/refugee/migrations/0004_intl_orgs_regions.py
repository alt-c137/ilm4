"""Международные организации помощи + регионы для уже заведённых записей.

Только официальные сайты; телефоны не указываем — они различаются по странам
(на сайтах есть раздел «контакты» по стране). Админ может править и дополнять.
"""
from django.db import migrations

INTL = [
    ('УВКБ ООН — Управление ООН по делам беженцев', 'https://www.unhcr.org/',
     'Статус беженца, защита, переселение в третьи страны. Главная организация ООН по делам беженцев.'),
    ('УВКБ ООН · Help — помощь по странам', 'https://help.unhcr.org/',
     'Выберите страну — там написано, как подать на убежище, куда обращаться и какие у вас права.'),
    ('МОМ — Международная организация по миграции', 'https://www.iom.int/',
     'Помощь мигрантам, добровольное возвращение домой, защита от торговли людьми.'),
    ('Красный Крест: восстановление семейных связей', 'https://familylinks.icrc.org/',
     'Поиск родственников, потерянных из-за войны, стихийных бедствий или миграции.'),
    ('Красный Крест и Красный Полумесяц (IFRC)', 'https://www.ifrc.org/',
     'Национальные общества Красного Полумесяца и Красного Креста есть почти в каждой стране.'),
    ('ЮНИСЕФ — Детский фонд ООН', 'https://www.unicef.org/',
     'Защита и помощь детям-беженцам и детям-мигрантам.'),
    ('Международный комитет спасения (IRC)', 'https://www.rescue.org/',
     'Экстренная помощь, здоровье, образование и поддержка при переселении.'),
    ('Норвежский совет по делам беженцев (NRC)', 'https://www.nrc.no/',
     'Жильё, образование, юридическая помощь с документами в кризисных регионах.'),
    ('Amnesty International', 'https://www.amnesty.org/',
     'Правозащитная организация: если нарушают ваши права — здесь можно сообщить.'),
]

EUROPE = [
    ('Евросоюз', 'Агентство ЕС по вопросам убежища (EUAA)', 'https://euaa.europa.eu/', 'ngo',
     'Официальная информация о процедуре убежища в странах Евросоюза.'),
    ('Евросоюз', 'AIDA — база данных о процедуре убежища', 'https://asylumineurope.org/', 'ngo',
     'Как устроено убежище в каждой стране Европы: сроки, права, жильё. Проект ECRE.'),
    ('Германия', 'PRO ASYL — помощь беженцам', 'https://www.proasyl.de/', 'ngo',
     'Общественная организация: консультации и защита прав беженцев в Германии.'),
]


def forward(apps, schema_editor):
    Org = apps.get_model('refugee', 'Org')
    by_country = {
        'Германия': 'europe', 'Россия': 'europe', 'Евросоюз': 'europe',
        'Казахстан': 'asia', 'Узбекистан': 'asia', 'Турция': 'asia',
    }
    for o in Org.objects.filter(region=''):
        o.region = by_country.get(o.country, '')
        o.save(update_fields=['region'])
    for name, url, notes in INTL:
        Org.objects.get_or_create(name=name, defaults={
            'country': 'Весь мир', 'kind': 'intl', 'region': 'intl', 'website': url, 'notes': notes})
    for country, name, url, kind, notes in EUROPE:
        Org.objects.get_or_create(name=name, defaults={
            'country': country, 'kind': kind, 'region': 'europe', 'website': url, 'notes': notes})


def backward(apps, schema_editor):
    Org = apps.get_model('refugee', 'Org')
    Org.objects.filter(name__in=[n for n, _, _ in INTL] + [n for _, n, _, _, _ in EUROPE]).delete()


class Migration(migrations.Migration):
    dependencies = [('refugee', '0003_region_lawyers')]
    operations = [migrations.RunPython(forward, backward)]
