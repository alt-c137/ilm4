from django.urls import path

from . import views

app_name = 'market'

urlpatterns = [
    path('', views.listing_list, name='list'),
    path('add/', views.listing_create, name='create'),
    path('my/', views.my_listings, name='my'),
    path('<int:pk>/boost/', views.listing_boost, name='boost'),
    path('<int:pk>/', views.listing_detail, name='detail'),
]
