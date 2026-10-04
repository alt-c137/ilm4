from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    path('', views.feed, name='feed'),
    path('new/', views.post_new, name='post_new'),
    path('like/', views.like, name='like'),
    path('save/', views.save, name='save'),
    path('saved/', views.saved, name='saved'),
    path('requests/', views.requests_view, name='requests'),
    path('comment/', views.comment, name='comment'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('post/<int:pk>/', views.post_detail, name='post'),
    path('post/<int:pk>/<str:action>/', views.post_act, name='post_act'),
    path('c/<str:target>/', views.target_comments, name='comments'),
    path('follow/<int:user_id>/', views.follow, name='follow'),
    path('stories/new/', views.story_new, name='story_new'),
    path('stories/<int:pk>/<str:action>/', views.story_act, name='story_act'),
]
