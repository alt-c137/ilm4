from django.db import migrations


def forward(apps, schema_editor):
    S = apps.get_model('core', 'SocialLink')
    S.objects.get_or_create(url='https://t.me/ilm4_info',
                            defaults={'kind': 'telegram', 'title': 'новости', 'order': 0})


def backward(apps, schema_editor):
    apps.get_model('core', 'SocialLink').objects.filter(url='https://t.me/ilm4_info').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0011_social_links')]
    operations = [migrations.RunPython(forward, backward)]
