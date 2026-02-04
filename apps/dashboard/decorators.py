from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

def is_staff_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name="staff").exists():
        return True
    profile = getattr(user, "profile", None)
    if profile and profile.position in {"manager", "leader", "ceo"}:
        return True
    return False


def dashboard_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not is_staff_user(request.user):
            return redirect("accounts:doctor_report")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
