from django.urls import path

from . import views

app_name = 'metrics'

urlpatterns = [
    path('m/', views.beat, name='beat'),
    path('moderation/stats/', views.stats, name='stats'),
]
