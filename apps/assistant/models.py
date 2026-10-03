"""ИИ-помощник: настройки человека (поставщик, свой ключ — зашифрован, разрешения), разговоры, подписка."""
from django.conf import settings
from django.db import models


class AssistantKey(models.Model):
    """Настройки помощника у человека: чей ИИ (свой ключ — без дневного лимита площадки) и что ему разрешено."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_key')
    provider = models.CharField('поставщик ИИ', max_length=20, default='anthropic')     # ключ из providers.PRESETS
    key_enc = models.TextField('ключ (зашифрован)', blank=True)
    hint = models.CharField('последние знаки ключа', max_length=12, blank=True)
    model = models.CharField('модель', max_length=80, blank=True)                       # пусто — модель поставщика по умолчанию
    base_url = models.CharField('адрес API (для своего сервера)', max_length=200, blank=True)
    read_chats = models.BooleanField('помощник может читать мои новые сообщения', default=False,
                                     help_text='Тексты уходят поставщику ИИ. Чаты никяха не передаются никогда.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'настройки ИИ-помощника'
        verbose_name_plural = 'настройки ИИ-помощника'


class AssistantPlan(models.Model):
    """Подписка на помощника (основа под «свои тарифы»): пока действует — без дневного лимита на ключе площадки.
    Сейчас выдаётся в админке; с оплатой из кошелька будет продлеваться сама."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_plan')
    until = models.DateField('без лимита до (включительно)', null=True, blank=True)
    extra_daily = models.PositiveSmallIntegerField('плюс сообщений в день', default=0)
    note = models.CharField('заметка', max_length=120, blank=True)

    class Meta:
        verbose_name = 'подписка на ИИ-помощника'
        verbose_name_plural = 'подписки на ИИ-помощника'


class Chat(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_chats')
    title = models.CharField(max_length=80, blank=True)
    api = models.CharField('формат истории', max_length=10, default='anthropic')        # anthropic | openai — у них разный вид сообщений
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'разговор с помощником'
        verbose_name_plural = 'разговоры с помощником'


class Turn(models.Model):
    """Шаг разговора в том виде, в каком его принимает API поставщика. История только дописывается.
    Claude: role + список блоков; OpenAI-совместимые: список готовых сообщений (role user / assistant / tool)."""

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='turns')
    role = models.CharField(max_length=10)                 # user | assistant | tool
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pk']
