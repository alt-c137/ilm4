from django.urls import path

from . import views, views_rooms, views_tg

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/', views.thread_start, name='start'),
    path('support/', views.support, name='support'),
    path('people/', views.people, name='people'),
    path('new/', views_rooms.room_new, name='room_new'),
    path('saved/', views_tg.saved, name='saved'),
    path('find/', views_tg.find, name='find'),
    path('folders/', views_tg.folder_list, name='folders'),
    path('folders/new/', views_tg.folder_edit, name='folder_new'),
    path('folders/<int:pk>/', views_tg.folder_edit, name='folder_edit'),
    path('pick/', views_tg.pick, name='pick'),
    path('forward/', views_tg.forward, name='forward'),
    path('<int:pk>/state/<str:action>/', views_tg.state, name='state'),
    path('<int:pk>/draft/', views_tg.draft, name='draft'),
    path('<int:pk>/search/', views_tg.search, name='search'),
    path('<int:pk>/post/<int:msg_id>/', views_tg.post, name='post'),
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
