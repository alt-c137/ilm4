"""API мобильного приложения: /api/v1/… (JSON, вход по токену)."""
from django.urls import path

from . import views_account as a
from . import views_chat as c
from . import views_content as v
from . import views_nikah as n
from . import views_pubs as m

app_name = 'api'

urlpatterns = [
    path('config/', a.config),
    path('home/', a.home),
    path('auth/login/', a.login),
    path('auth/register/', a.register),
    path('auth/logout/', a.logout),
    path('auth/password-reset/', a.password_reset),
    path('auth/telegram/start/', a.telegram_start),
    path('auth/telegram/poll/', a.telegram_poll),
    path('auth/web-link/', a.web_link),
    path('auth/web/<str:code>/', a.web_enter),
    path('auth/phone/', a.phone_start),
    path('auth/phone/status/', a.phone_status),
    path('me/', a.me),
    path('push/', a.push_register),
    path('notifications/', a.notifications),
    path('notifications/read/', a.notifications_read),
    path('wallet/', a.wallet),
    path('report/', a.report),
    path('block/', a.block),

    path('news/', v.news),
    path('news/<int:pk>/', v.news_detail),
    path('places/map/', v.places_map),
    path('my/', m.my),
    path('my/<str:key>/<int:pk>/', m.my_item),
    path('pubs/<str:key>/form/', m.form_schema),
    path('pubs/<str:key>/save/', m.save),
    path('pubs/<str:key>/', v.pubs),
    path('pubs/<str:key>/<int:pk>/', v.pub_detail),
    path('pubs/<str:key>/<int:pk>/message/', v.pub_message),
    path('forum/<int:pk>/reply/', v.topic_reply),

    path('nikah/state/', n.state),
    path('nikah/options/', n.options),
    path('nikah/profile/', n.profile_save),
    path('nikah/profile/raw/', n.profile_raw),
    path('nikah/pause/', n.pause),
    path('nikah/feed/', n.feed),
    path('nikah/lists/', n.lists),
    path('nikah/restore/', n.restore),
    path('nikah/premium/', n.premium),
    path('nikah/p/<int:pk>/', n.profile_detail),
    path('nikah/p/<int:pk>/skip/', n.skip),
    path('nikah/p/<int:pk>/interest/', n.interest),
    path('nikah/p/<int:pk>/save/', n.save_toggle),
    path('nikah/match/<int:pk>/', n.match),
    path('nikah/match/<int:pk>/open/', n.match_open),
    path('nikah/match/<int:pk>/photo/', n.match_photo),
    path('nikah/match/<int:pk>/decide/', n.match_decide),
    path('nikah/match/<int:pk>/pay/', n.match_pay),

    path('chat/', c.threads),
    path('chat/file/<int:msg_id>/', c.file),
    path('chat/<int:pk>/', c.messages),
    path('chat/<int:pk>/send/', c.send),
    path('chat/<int:pk>/upload/', c.upload),
    path('chat/<int:pk>/read/', c.read),
]
