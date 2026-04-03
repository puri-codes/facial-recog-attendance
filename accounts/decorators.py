from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden


def role_required(*roles):
    """Decorator that restricts view access to specific user roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to access this page.')
                return HttpResponseForbidden('Access Denied')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_required(view_func):
    """Restrict access to admin users only."""
    return role_required('admin')(view_func)


def teacher_required(view_func):
    """Restrict access to teacher users only."""
    return role_required('teacher')(view_func)


def student_required(view_func):
    """Restrict access to student users only."""
    return role_required('student')(view_func)


def admin_or_teacher_required(view_func):
    """Restrict access to admin or teacher users."""
    return role_required('admin', 'teacher')(view_func)
