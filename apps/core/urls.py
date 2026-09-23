from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('rules/', TemplateView.as_view(template_name='core/pages/rules.html'), name='rules'),
    path('privacy/', TemplateView.as_view(template_name='core/pages/privacy.html'), name='privacy'),
    path('support/', TemplateView.as_view(template_name='core/pages/support.html'), name='support'),
    path('soon/', views.soon, name='soon'),
    path('catalog/', views.catalog, name='catalog'),
    path('settings/', views.settings_view, name='settings'),
    path('feed/', views.feed, name='feed'),
    path('islam/', TemplateView.as_view(template_name='core/pages/islam.html'), name='shahada'),
    path('salah/', TemplateView.as_view(template_name='core/pages/salah.html'), name='salah'),
]
