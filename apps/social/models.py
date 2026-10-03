"""Соцсеть ilm4 — как во ВКонтакте и Telegram: записи на стене и лента, подписки, лайки и комментарии,
сторис на 24 часа, короткие видео (ilm4-shorts) и подарки.

Лента и записи работают сейчас. Сторис, короткие видео и подарки — основа: таблицы, правила и API готовы,
включаются выключателем раздела в админке (ModuleConfig 'stories' / 'shorts' / 'gifts'), когда будут мощности
для хранения и раздачи видео. Код при этом переделывать не придётся.

Лайки и комментарии — общие для любого объекта ленты: «цель» — строка вида 'post:12', 'buy:5', 'news:3'.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

ALL, CLOSE = 'all', 'close'
VISIBILITY = [(ALL, _lazy('Все')), (CLOSE, _lazy('Близкие друзья'))]


class Post(models.Model):
    """Запись на стене человека (как во ВКонтакте): текст и до 10 фото. Видна всем или только близким друзьям."""

    MAX_PHOTOS = 10
    MAX_TEXT = 4000

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    text = models.TextField('текст', blank=True, max_length=MAX_TEXT)
    privacy = models.CharField('кто видит', max_length=6, choices=VISIBILITY, default=ALL)
    repost_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='reposts_set',
                                  verbose_name='репост записи')
    likes = models.PositiveIntegerField('лайков', default=0)
    comments = models.PositiveIntegerField('комментариев', default=0)
    reposts = models.PositiveIntegerField('репостов', default=0)
    views = models.PositiveIntegerField('просмотров', default=0)
    hidden = models.BooleanField('скрыта модератором', default=False, db_index=True)
    created_at = models.DateTimeField('создана', auto_now_add=True, db_index=True)
    edited_at = models.DateTimeField('изменена', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'запись'
        verbose_name_plural = 'записи'

    def __str__(self):
        return f'{self.author}: {self.text[:40]}'

    @property
    def key(self) -> str:
        return f'post:{self.pk}'


class PostPhoto(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField('фото', upload_to='posts/%Y/%m/')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'фото записи'
        verbose_name_plural = 'фото записей'


class Follow(models.Model):
    """Подписка на человека: его записи и сторис — в разделе «Подписки» ленты."""

    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['follower', 'author'], name='one_follow')]
        verbose_name = 'подписка'
        verbose_name_plural = 'подписки'


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes_given')
    target = models.CharField('что', max_length=40, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'target'], name='one_like')]
        verbose_name = 'лайк'
        verbose_name_plural = 'лайки'


class Saved(models.Model):
    """«Сохранить» — закладка на карточку ленты (видит только сам человек). Вместе с лайками говорит, что ему интересно."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_items')
    target = models.CharField('что', max_length=40, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'target'], name='one_saved')]
        ordering = ['-pk']
        verbose_name = 'сохранённое'
        verbose_name_plural = 'сохранённое'


class Comment(models.Model):
    """Комментарий к записи или публикации в ленте."""

    MAX_TEXT = 2000

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feed_comments')
    target = models.CharField('к чему', max_length=40, db_index=True)
    text = models.TextField('текст', max_length=MAX_TEXT)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    hidden = models.BooleanField('скрыт', default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'комментарий'
        verbose_name_plural = 'комментарии'


class Story(models.Model):
    """Сторис на 24 часа — фото (видео — когда включат хранилище для видео)."""

    PHOTO, VIDEO = 'photo', 'video'
    HOURS = 24

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories_posted')
    kind = models.CharField(max_length=6, choices=[(PHOTO, _lazy('Фото')), (VIDEO, _lazy('Видео'))], default=PHOTO)
    media = models.FileField('файл', upload_to='stories/%Y/%m/')
    caption = models.CharField('подпись', max_length=200, blank=True)
    privacy = models.CharField('кто видит', max_length=6, choices=VISIBILITY, default=ALL)
    views = models.PositiveIntegerField('просмотров', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField('исчезнет', db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'сторис'
        verbose_name_plural = 'сторис'


class StoryView(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='seen_by')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories_seen')
    reaction = models.CharField(max_length=16, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['story', 'user'], name='one_story_view')]


class Short(models.Model):
    """Короткое вертикальное видео (ilm4-shorts). Проходит модерацию перед показом."""

    PENDING, APPROVED, REJECTED = 'pending', 'approved', 'rejected'
    MAX_SECONDS = 90

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shorts')
    video = models.FileField('видео', upload_to='shorts/%Y/%m/')
    cover = models.ImageField('обложка', upload_to='shorts/%Y/%m/', blank=True, null=True)
    caption = models.CharField('подпись', max_length=500, blank=True)
    duration = models.PositiveIntegerField('длительность, сек', default=0)
    status = models.CharField(max_length=9, choices=[(PENDING, _lazy('на проверке')), (APPROVED, _lazy('опубликовано')),
                                                     (REJECTED, _lazy('отклонено'))], default=PENDING, db_index=True)
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'короткое видео'
        verbose_name_plural = 'короткие видео'


class Gift(models.Model):
    """Подарок из каталога (как подарки в Telegram): значок или картинка и цена. Цены и набор — в админке."""

    title = models.CharField('название', max_length=60)
    emoji = models.CharField('значок', max_length=8, blank=True)
    image = models.ImageField('картинка', upload_to='gifts/', blank=True, null=True)
    price = models.PositiveIntegerField('цена, сум', default=0, help_text='0 — бесплатный')
    active = models.BooleanField('в каталоге', default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'price', 'pk']
        verbose_name = 'подарок (каталог)'
        verbose_name_plural = 'подарки (каталог)'

    def __str__(self):
        return f'{self.emoji} {self.title}'


class UserGift(models.Model):
    gift = models.ForeignKey(Gift, on_delete=models.PROTECT, related_name='sent')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='gifts_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gifts_received')
    message = models.CharField('подпись', max_length=200, blank=True)
    anonymous = models.BooleanField('скрыть отправителя', default=False)
    on_profile = models.BooleanField('показывать в профиле', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'подарок'
        verbose_name_plural = 'подарки'
