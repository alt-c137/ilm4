from django.urls import path

from . import views

app_name = 'refugee'

urlpatterns = [
    path('', views.index, name='index'),
]
