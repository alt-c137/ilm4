from django.urls import path

from . import views_spaces as views

app_name = 'spaces'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.new, name='new'),
    path('join/<str:code>/', views.join, name='join'),
    path('<int:pk>/', views.space, name='space'),
    path('<int:pk>/act/', views.act, name='act'),
    path('<int:pk>/board/', views.board, name='board'),
    path('<int:pk>/voice/<int:voice_id>/', views.voice_room, name='voice'),
]
