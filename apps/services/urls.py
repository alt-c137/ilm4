from django.urls import path

from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('add/', views.service_create, name='create'),
]
