from django.urls import path

from . import views

app_name = 'deals'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.new, name='new'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/<str:action>/', views.act, name='act'),
]
