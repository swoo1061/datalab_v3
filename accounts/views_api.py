from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
import json

from .models import UserProfile

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
import json

from .models import UserProfile


@csrf_exempt
def login_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return JsonResponse({"error": "missing credentials"}, status=400)

    try:
        user_obj = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    # ✅ 1) superuser는 profile/승인 체크 없이 바로 통과
    if user_obj.is_superuser:
        user = authenticate(request, username=username, password=password)
        if not user:
            return JsonResponse({"error": "invalid credentials"}, status=401)
        login(request, user)
        if not request.session.session_key:
            request.session.save()
        return JsonResponse({"ok": True, "session_key": request.session.session_key})

    # ✅ 2) 일반 유저는 profile 존재/승인 체크
    try:
        profile = user_obj.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "profile_missing"}, status=403)

    if not profile.is_approved:
        return JsonResponse({"error": "approval_pending"}, status=403)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    login(request, user)
    if not request.session.session_key:
        request.session.save()
    return JsonResponse({"ok": True, "session_key": request.session.session_key})


@csrf_exempt
def me_api(request):
    user = request.user

    # 🔥 redirect 절대 발생 금지
    if not user.is_authenticated:
        return JsonResponse(
            {"error": "not_authenticated"},
            status=401
        )

    try:
        p = user.profile
    except Exception:
        if user.is_superuser:
            return JsonResponse(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "name": user.get_full_name() or user.username,
                    "birth_date": None,
                    "phone": None,
                    "position": "admin",
                    "is_approved": True,
                },
                json_dumps_params={"ensure_ascii": False},
            )
        return JsonResponse(
            {"error": "profile_missing"},
            status=403
        )

    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": p.name,
            "birth_date": p.birth_date,
            "phone": p.phone,
            "position": p.position,
            "is_approved": p.is_approved,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def logout_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    logout(request)
    return JsonResponse({"ok": True})


@csrf_exempt
def api_signup(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    data = json.loads(request.body or "{}")
    print("🔥 SIGNUP DATA:", data) # 디버깅용 로그

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    name = data.get("name")
    position = data.get("position")
    birth_date = data.get("birth_date")
    phone = data.get("phone")

    if not all([username, password, email, name, position]):
        return JsonResponse({"error": "missing fields"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "username exists"}, status=400)

    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            is_active=False,
        )

        UserProfile.objects.create(
            user=user,
            name=name,
            position=position,
            is_approved=False,
            birth_date=birth_date or None,
            phone=phone,
        )

    return JsonResponse({"ok": True})




