from django.urls import path

from . import views

app_name = 'health'

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_doctor, name='add'),
    path('<int:pk>/', views.detail, name='detail'),
]
