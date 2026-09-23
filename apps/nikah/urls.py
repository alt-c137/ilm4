from django.urls import path

from . import views

app_name = 'nikah'

urlpatterns = [
    path('', views.home, name='home'),
    path('how/', views.how, name='how'),
    path('create/', views.create, name='create'),
    path('edit/', views.edit, name='edit'),
    path('me/', views.mine, name='mine'),
    path('me/boost/', views.boost, name='boost'),
    path('me/pause/', views.pause, name='pause'),
    path('filters/', views.filters, name='filters'),
    path('restore/', views.restore, name='restore'),
    path('premium/', views.premium, name='premium'),
    path('interests/', views.interests, name='interests'),
    path('saved/', views.saved, name='saved'),
    path('chats/', views.chats, name='chats'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/interest/', views.interest, name='interest'),
    path('<int:pk>/save/', views.save_toggle, name='save'),
    path('<int:pk>/skip/', views.skip, name='skip'),
    path('match/<int:pk>/', views.match, name='match'),
    path('match/<int:pk>/open/', views.match_open, name='match_open'),
    path('match/<int:pk>/photo/', views.match_photo, name='match_photo'),
    path('match/<int:pk>/decide/', views.match_decide, name='match_decide'),
    path('match/<int:pk>/pay/', views.match_pay, name='match_pay'),
    path('moderation/photo/<int:pk>/', views.admin_photo, name='admin_photo'),
]
