from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/', views.thread_start, name='start'),
    path('<int:pk>/', views.thread_detail, name='thread'),
]
