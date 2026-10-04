from django.urls import path

from . import google, telegram, views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google/', google.google_start, name='google'),
    path('google/callback/', google.google_callback, name='google_callback'),
    path('telegram/webapp/', telegram.webapp_login, name='telegram_webapp'),
    path('telegram/poll/', views.tg_poll, name='tg_poll'),
    path('register/', views.register, name='register'),
    path('password/reset/', views.password_reset, name='password_reset'),
    path('password/reset/sent/', views.password_reset_done, name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password/reset/complete/', views.password_reset_complete, name='password_reset_complete'),
    path('profile/', views.profile, name='profile'),
    path('photos/', views.photos, name='photos'),
    path('u/<int:pk>/', views.public_profile, name='public'),
    path('u/<int:pk>/block/', views.block_toggle, name='block'),
    path('u/<int:pk>/close/', views.close_toggle, name='close'),
    path('ping/', views.ping, name='ping'),
    path('blocked/', views.blocked_list, name='blocked'),
    path('personas/', views.personas_view, name='personas'),
    path('devices/', views.devices_view, name='devices'),
    path('qr/new/', views.qr_start, name='qr_start'),
    path('qr/status/', views.qr_status, name='qr_status'),
    path('qr/<str:token>/', views.qr_confirm, name='qr_confirm'),
    path('accounts/', views.accounts_view, name='accounts'),
    path('accounts/switch/', views.accounts_switch, name='accounts_switch'),
    path('delete/', views.delete_account, name='delete'),
    path('phone/', views.phone, name='phone'),
    path('phone/status/', views.phone_status, name='phone_status'),
    path('2fa/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
]
