from django.urls import path

from . import views

app_name = 'maps'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('add/', views.add_place, name='add'),
]
