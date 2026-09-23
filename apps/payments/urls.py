from django.urls import path

from . import callbacks, views

app_name = 'payments'

urlpatterns = [
    path('click/prepare/', callbacks.click_prepare, name='click_prepare'),
    path('click/complete/', callbacks.click_complete, name='click_complete'),
    path('stripe/webhook/', callbacks.stripe_webhook, name='stripe_webhook'),
    path('crypto/ipn/', callbacks.crypto_ipn, name='crypto_ipn'),
    path('done/<int:pk>/', views.done, name='done'),
]
