"""Роли и проверки доступа (PASSPORT §3). Права проверяем в view, не только в меню."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def role_required(*roles: str):
    """Пропустить только аутентифицированных с одной из ролей (или супер-админа)."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or request.user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied
        return wrapped
    return decorator


# Готовые уровни доступа для разделов
admin_required = role_required(User.ROLE_ADMIN, User.ROLE_SUPER)
support_required = role_required(User.ROLE_SUPPORT, User.ROLE_ADMIN, User.ROLE_SUPER)
