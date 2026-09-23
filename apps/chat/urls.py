from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/', views.thread_start, name='start'),
    path('contacts/', views.contacts, name='contacts'),
    path('contacts/match/', views.contacts_match, name='contacts_match'),
    path('<int:pk>/', views.thread_detail, name='thread'),
    path('<int:pk>/upload/', views.upload, name='upload'),
    path('file/<int:msg_id>/', views.attachment, name='file'),
]
