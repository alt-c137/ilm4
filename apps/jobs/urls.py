from django.urls import path

from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.vacancy_list, name='list'),
    path('add/', views.vacancy_create, name='create'),
    path('<int:pk>/', views.vacancy_detail, name='detail'),
    path('<int:pk>/respond/', views.vacancy_respond, name='respond'),
]
