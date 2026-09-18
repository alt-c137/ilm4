from django.urls import path

from . import views

app_name = 'nikah'

urlpatterns = [
    path('', views.profile_list, name='list'),
    path('create/', views.profile_create, name='create'),
    path('mine/', views.mine, name='mine'),
    path('boost/', views.boost, name='boost'),
    path('<int:pk>/', views.profile_detail, name='detail'),
    path('<int:pk>/contact/', views.open_contact, name='contact'),
]
