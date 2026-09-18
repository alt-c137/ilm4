"""Вход по email или имени пользователя (email — основной способ)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and '@' in username:
            try:
                user = get_user_model().objects.get(email__iexact=username)
            except get_user_model().DoesNotExist:
                return None
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)
