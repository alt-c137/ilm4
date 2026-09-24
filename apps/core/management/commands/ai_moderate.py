"""ИИ-проверка всего, что ждёт модерации. Сервис jobs запускает раз в минуту.
    python manage.py ai_moderate [--limit 20]
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.core import ai_moderation as ai
from apps.core.models import AIReview, Moderation, SiteSettings
from apps.core.publications import PUBLICATIONS

LABEL = {'ok': '✅ чисто', 'review': '🟡 посмотреть', 'reject': '⛔ нарушение', 'error': '⚠️ ошибка ИИ'}


def _text_of(obj) -> str:
    """Все текстовые поля объекта одним текстом."""
    parts = []
    for f in obj._meta.concrete_fields:
        if f.get_internal_type() in ('CharField', 'TextField') and f.name not in ('status', 'photo_mode') \
                and not f.choices:
            value = getattr(obj, f.name, '')
            if value:
                parts.append(f'{f.verbose_name}: {value}')
    return '\n'.join(parts)


def _items():
    for pub in PUBLICATIONS:
        for obj in pub.get_model().objects.filter(status=Moderation.PENDING).order_by('pk')[:200]:
            yield obj, pub.label, False
    from apps.nikah.models import NikahProfile
    for p in NikahProfile.objects.filter(status=Moderation.PENDING).order_by('pk')[:200]:
        yield p, 'Анкета никяха', True


class Command(BaseCommand):
    help = 'ИИ-модерация: проверить публикации и анкеты «на проверке»'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, limit=20, **opts):
        if not ai.enabled():
            self.stdout.write('ИИ-модерация выключена или нет ключа — пропуск')
            return
        st = SiteSettings.get_solo()
        done = 0
        for obj, label, is_nikah in _items():
            if done >= limit:
                break
            text = _text_of(obj)
            if is_nikah:
                text = f'Возраст: {obj.age}\n' + text
            image = None
            if is_nikah and st.ai_check_photos and obj.has_photo:
                from apps.chat.crypto import decrypt_bytes
                with obj.photo_private.open('rb') as f:
                    image = decrypt_bytes(f.read())
            h = ai.content_hash(text, image or b'')
            ct = ContentType.objects.get_for_model(obj)
            prev = AIReview.objects.filter(content_type=ct, object_id=obj.pk).first()
            if prev and prev.content_hash == h and prev.verdict != 'error':
                continue                                   # уже проверено, не менялось
            res = ai.check(text, image, contacts_forbidden=is_nikah)
            AIReview.objects.update_or_create(content_type=ct, object_id=obj.pk, defaults={
                'content_hash': h, 'verdict': res['verdict'], 'reasons': res['reasons'], 'model_name': res['model']})
            done += 1
            if res['verdict'] == 'ok' and st.ai_auto_approve:
                self._approve(obj, is_nikah)
            self._tell_moderators(obj, label, res)
        self.stdout.write(f'Проверено ИИ: {done}')

    def _approve(self, obj, is_nikah):
        if is_nikah:
            from apps.nikah.bot import approve
            approve(obj)
        else:
            from apps.core.signals import set_status
            set_status(type(obj).objects.filter(pk=obj.pk), Moderation.APPROVED)

    def _tell_moderators(self, obj, label, res):
        from apps.accounts.telegram import api
        from apps.tgbot.dispatch import moderation_chat
        chat = moderation_chat()
        if not chat:
            return
        why = ('\n• ' + '\n• '.join(res['reasons'])) if res['reasons'] else ''
        api('sendMessage', {'chat_id': chat, 'text': f'🤖 ИИ: {label} #{obj.pk} — {LABEL.get(res["verdict"], "")}{why}'})
