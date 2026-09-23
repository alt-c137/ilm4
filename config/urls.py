"""Корневые URL ilm4: админка + ядро. Разделы подключают свои urls по фазам."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'ilm4 — управление'
admin.site.site_title = 'ilm4 админ'

urlpatterns = [
    path('admin/', admin.site.urls),
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
    path('refugee/', include('apps.refugee.urls')),
    path('transport/', include('apps.transport.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('deals/', include('apps.deals.urls')),
    path('notifications/', include('apps.core.notification_urls')),
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
