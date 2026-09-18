"""Корневые URL ilm4: админка + ядро. Разделы подключают свои urls по фазам."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'ilm4 — управление'
admin.site.site_title = 'ilm4 админ'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
