from django.urls import path

from . import views

app_name = 'migration'

urlpatterns = [
    path('', views.story_list, name='list'),
    path('add/', views.story_create, name='create'),
    path('<int:pk>/', views.story_detail, name='detail'),
]
