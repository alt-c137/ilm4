"""Уведомления (колокольчик)."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path

app_name = 'notifications'


@login_required
def notification_list(request):
    notifications = request.user.notifications.select_related('user')[:50]
    return render(request, 'core/notifications.html', {'notifications': notifications})


@login_required
def notification_read_all(request):
    if request.method == 'POST':
        request.user.notifications.filter(read=False).update(read=True)
    return redirect('notifications:list')


urlpatterns = [
    path('', notification_list, name='list'),
    path('read-all/', notification_read_all, name='read-all'),
]
