from django.urls import path

from . import views

app_name = 'transport'

urlpatterns = [
    path('', views.ride_list, name='list'),
    path('add/', views.ride_create, name='create'),
]
