from django.urls import path

from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.topic_list, name='list'),
    path('ask/', views.topic_create, name='create'),
    path('<int:pk>/', views.topic_detail, name='detail'),
    path('<int:pk>/reply/', views.reply_create, name='reply'),
]
