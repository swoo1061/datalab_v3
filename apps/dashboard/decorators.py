from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.data.permissions import can_access_web_dashboard

def is_staff_user(user):
    return can_access_web_dashboard(user)


def dashboard_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not is_staff_user(request.user):
            return render(request, "core/forbidden.html", status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped_view
