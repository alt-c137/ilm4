from django.urls import path

from . import views

app_name = 'library'

urlpatterns = [
    path('', views.book_list, name='list'),
    path('add/', views.book_add, name='add'),
    path('<int:pk>/download/', views.book_download, name='download'),
]
