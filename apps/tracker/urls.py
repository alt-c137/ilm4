from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.habit_new, name='new'),
    path('stats/', views.stats, name='stats'),
    path('h/<int:pk>/', views.habit_edit, name='edit'),
    path('h/<int:pk>/log/', views.log, name='log'),
    path('b/new/', views.board_new, name='board_new'),
    path('b/<int:pk>/', views.board, name='board'),
    path('join/<str:code>/', views.join, name='join'),
]
