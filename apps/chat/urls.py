from django.urls import path

from . import views, views_rooms

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/', views.thread_start, name='start'),
    path('support/', views.support, name='support'),
    path('people/', views.people, name='people'),
    path('new/', views_rooms.room_new, name='room_new'),
    path('channels/', views_rooms.channels, name='channels'),
    path('join/<str:code>/', views_rooms.room_join_link, name='room_join'),
    path('<int:pk>/info/', views_rooms.room_info, name='room_info'),
    path('<int:pk>/mute/', views.mute, name='mute'),
    path('<int:pk>/room/<str:action>/', views_rooms.room_act, name='room_act'),
    path('<int:pk>/member/<int:user_id>/<str:action>/', views_rooms.room_member, name='room_member'),
    path('contacts/', views.contacts, name='contacts'),
    path('contacts/match/', views.contacts_match, name='contacts_match'),
    path('<int:pk>/', views.thread_detail, name='thread'),
    path('<int:pk>/upload/', views.upload, name='upload'),
    path('<int:pk>/upload/begin/', views.upload_begin, name='upload_begin'),
    path('upload/<uuid:upload_id>/', views.upload_chunk, name='upload_status'),
    path('upload/<uuid:upload_id>/<str:step>/', views.upload_chunk, name='upload_step'),
    path('file/<int:msg_id>/', views.attachment, name='file'),
    path('msg/<int:msg_id>/<str:action>/', views.scheduled_action, name='scheduled'),
]
