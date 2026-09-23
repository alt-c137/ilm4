from django.urls import path

from . import views

app_name = 'maps'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('add/', views.add_place, name='add'),
    path('<int:pk>/', views.place_detail, name='detail'),
    path('<int:pk>/confirm/', views.place_confirm, name='confirm'),
]
