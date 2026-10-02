from django.urls import path

from . import views

app_name = 'transport'

urlpatterns = [
    path('', views.ride_list, name='list'),
    path('add/', views.ride_create, name='create'),
    path('trips/', views.trip_list, name='trips'),
    path('trips/add/', views.trip_create, name='trip_create'),
    path('trips/<int:pk>/', views.trip_detail, name='trip'),
    path('trips/<int:pk>/request/', views.trip_request, name='trip_request'),
    path('trips/request/<int:req_id>/<str:action>/', views.trip_request_act, name='trip_request_act'),
]
