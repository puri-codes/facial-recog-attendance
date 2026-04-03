from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db import OperationalError, ProgrammingError


class BypassLoginMiddleware:
    """
    Auto-authenticate a local user when BYPASS_LOGIN is enabled.
    Useful for local/demo environments where login should be skipped.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bypass_paused = request.session.get('bypass_login_paused', False)
        if (
            getattr(settings, 'BYPASS_LOGIN', False)
            and not bypass_paused
            and not request.user.is_authenticated
        ):
            user = self._get_bypass_user()
            if user:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return self.get_response(request)

    def _get_bypass_user(self):
        try:
            User = get_user_model()
            username = getattr(settings, 'BYPASS_LOGIN_USERNAME', 'admin')

            user = User.objects.filter(username=username, is_active=True).first()
            if user:
                return user

            # Fallbacks if requested username is missing.
            user = User.objects.filter(is_superuser=True, is_active=True).first()
            if user:
                return user

            if hasattr(User, 'role'):
                user = User.objects.filter(role='admin', is_active=True).first()
                if user:
                    return user

            user = User.objects.filter(is_active=True).first()
            if user:
                return user

            if getattr(settings, 'BYPASS_LOGIN_AUTO_CREATE_USER', True):
                user = User.objects.create(
                    username=username or 'local_admin',
                    is_active=True,
                    is_staff=True,
                    is_superuser=True,
                    **({'role': 'admin'} if hasattr(User, 'role') else {}),
                )
                user.set_unusable_password()
                user.save(update_fields=['password'])
                return user

            return None
        except (OperationalError, ProgrammingError):
            # DB might not be ready during first startup/migration.
            return None
