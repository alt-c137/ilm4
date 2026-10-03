from django.urls import path

from . import views

app_name = 'assistant'

urlpatterns = [
    path('', views.index, name='index'),
    path('c/<int:chat_id>/', views.index, name='chat'),
    path('c/<int:chat_id>/delete/', views.delete, name='delete'),
    path('send/', views.send, name='send'),
    path('key/', views.key, name='key'),
    path('prefs/', views.prefs, name='prefs'),
]
