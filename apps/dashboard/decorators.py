from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def is_staff_user(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="staff").exists()
    )


def dashboard_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not is_staff_user(request.user):
            return HttpResponseForbidden("Dashboard access denied")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
