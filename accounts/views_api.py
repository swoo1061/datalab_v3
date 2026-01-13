from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
import json

from .models import UserProfile

@csrf_exempt
def login_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    import json
    data = json.loads(request.body or "{}")
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return JsonResponse({"error": "missing credentials"}, status=400)

    try:
        user_obj = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    # 🔥 핵심 방어 코드
    try:
        profile = user_obj.profile
    except UserProfile.DoesNotExist:
        return JsonResponse(
            {"error": "profile_missing"},
            status=403
        )

    if not profile.is_approved:
        return JsonResponse(
            {"error": "approval_pending"},
            status=403
        )

    user = authenticate(
        request,
        username=username,
        password=password,
    )

    if not user:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    login(request, user)
    return JsonResponse({"ok": True})

def me_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    u = request.user
    p = u.profile

    return JsonResponse(
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
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

