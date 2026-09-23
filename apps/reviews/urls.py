from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('<int:ct_id>/<int:obj_id>/', views.submit, name='submit'),
    path('reply/<int:pk>/', views.reply, name='reply'),
]
