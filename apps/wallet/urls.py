from django.urls import path

from apps.payments import views as pay_views

from . import views

app_name = 'wallet'

urlpatterns = [
    path('', views.index, name='index'),
    path('payout/', views.payout, name='payout'),
    path('topup/', pay_views.topup, name='topup'),
]
