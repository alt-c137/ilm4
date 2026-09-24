from django.urls import path
from django.views.generic import TemplateView

from . import my_views, views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('rules/', TemplateView.as_view(template_name='core/pages/rules.html'), name='rules'),
    path('privacy/', TemplateView.as_view(template_name='core/pages/privacy.html'), name='privacy'),
    path('support/', TemplateView.as_view(template_name='core/pages/support.html'), name='support'),
    path('soon/', views.soon, name='soon'),
    path('my/', my_views.my_publications, name='my'),
    path('my/<slug:key>/<int:pk>/edit/', my_views.my_edit, name='my_edit'),
    path('my/<slug:key>/<int:pk>/delete/', my_views.my_delete, name='my_delete'),
    path('my/<slug:key>/<int:pk>/toggle/', my_views.my_toggle, name='my_toggle'),
    path('report/', my_views.report, name='report'),
    path('lang/', views.set_language, name='set_lang'),
    path('catalog/', views.catalog, name='catalog'),
    path('settings/', views.settings_view, name='settings'),
    path('feed/', views.feed, name='feed'),
    path('islam/', TemplateView.as_view(template_name='core/pages/islam.html'), name='shahada'),
    path('salah/', TemplateView.as_view(template_name='core/pages/salah.html'), name='salah'),
]
