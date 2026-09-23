from django.urls import path

from . import google, views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google/', google.google_start, name='google'),
    path('google/callback/', google.google_callback, name='google_callback'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('u/<int:pk>/', views.public_profile, name='public'),
    path('2fa/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
]
