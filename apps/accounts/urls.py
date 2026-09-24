from django.urls import path

from . import google, telegram, views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google/', google.google_start, name='google'),
    path('google/callback/', google.google_callback, name='google_callback'),
    path('telegram/webapp/', telegram.webapp_login, name='telegram_webapp'),
    path('register/', views.register, name='register'),
    path('password/reset/', views.password_reset, name='password_reset'),
    path('password/reset/sent/', views.password_reset_done, name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password/reset/complete/', views.password_reset_complete, name='password_reset_complete'),
    path('profile/', views.profile, name='profile'),
    path('u/<int:pk>/', views.public_profile, name='public'),
    path('u/<int:pk>/block/', views.block_toggle, name='block'),
    path('blocked/', views.blocked_list, name='blocked'),
    path('delete/', views.delete_account, name='delete'),
    path('phone/', views.phone, name='phone'),
    path('phone/status/', views.phone_status, name='phone_status'),
    path('2fa/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
]
