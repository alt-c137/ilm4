"""Корневые URL ilm4: админка + ядро. Разделы подключают свои urls по фазам."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path

from apps.chat.views_rooms import public_page as chat_public_page
from apps.chat.views_tg import by_handle as chat_by_handle
from apps.core import seo

admin.site.site_header = 'ilm4 — управление'
admin.site.site_title = 'ilm4 админ'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', seo.robots),
    path('sitemap.xml', sitemap, {'sitemaps': seo.SITEMAPS}, name='sitemap'),
    path('sw.js', seo.service_worker),
    path('offline/', seo.offline),
    path('healthz/', seo.healthz),
    path('accounts/', include('apps.accounts.urls')),
    path('wallet/', include('apps.wallet.urls')),
    path('prayer/', include('apps.prayer.urls')),
    path('map/', include('apps.maps.urls')),
    path('health/', include('apps.health.urls')),
    path('buy/', include('apps.market.urls')),
    path('news/', include('apps.news.urls')),
    path('forum/', include('apps.forum.urls')),
    path('jobs/', include('apps.jobs.urls')),
    path('migration/', include('apps.migration.urls')),
    path('services/', include('apps.services.urls')),
    path('library/', include('apps.library.urls')),
    path('nikah/', include('apps.nikah.urls')),
    path('chat/', include('apps.chat.urls')),
    path('communities/', include('apps.chat.urls_spaces')),
    path('c/<str:handle>/', chat_public_page, name='channel_public'),
    re_path(r'^@(?P<handle>[A-Za-z][A-Za-z0-9_]{3,31})/?$', chat_by_handle, name='by_handle'),
    path('refugee/', include('apps.refugee.urls')),
    path('transport/', include('apps.transport.urls')),
    path('tracker/', include('apps.tracker.urls')),
    path('feed/', include('apps.social.urls')),
    path('assistant/', include('apps.assistant.urls')),
    path('', include('apps.metrics.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('deals/', include('apps.deals.urls')),
    path('payments/', include('apps.payments.urls')),
    path('tg/', include('apps.tgbot.urls')),
    path('api/v1/', include('apps.api.urls')),
    path('notifications/', include('apps.core.notification_urls')),
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
