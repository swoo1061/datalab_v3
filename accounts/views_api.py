from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
import json
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import UserProfile

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
import json

from .models import UserProfile


VALID_PRESENCE_STATUS = {"online", "away", "meeting", "dnd", "offline"}


def _get_user_from_session_header(request):
    session_key = request.headers.get("X-Sessionid")
    if not session_key:
        return None
    try:
        session = Session.objects.get(
            session_key=session_key,
            expire_date__gte=timezone.now()
        )
    except Session.DoesNotExist:
        return None
    user_id = session.get_decoded().get("_auth_user_id")
    if not user_id:
        return None
    UserModel = get_user_model()
    try:
        return UserModel.objects.get(pk=user_id)
    except UserModel.DoesNotExist:
        return None


def _resolve_request_user(request):
    user = request.user
    if user.is_authenticated:
        return user
    header_user = _get_user_from_session_header(request)
    if header_user and header_user.is_authenticated:
        return header_user
    return None


def _build_profile_image_url(request, profile):
    if not profile or not getattr(profile, "profile_image", None):
        return ""
    try:
        return request.build_absolute_uri(profile.profile_image.url)
    except Exception:
        return ""


def _normalize_presence_status(raw):
    value = str(raw or "").strip().lower()
    if value in VALID_PRESENCE_STATUS:
        return value
    return ""


def _mark_online_if_possible(user):
    if not user:
        return
    try:
        profile = user.profile
    except Exception:
        return
    profile.presence_status = "online"
    profile.presence_updated_at = timezone.now()
    profile.save(update_fields=["presence_status", "presence_updated_at"])


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
    remember = bool(data.get("remember"))

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
        if remember:
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)
        if not request.session.session_key:
            request.session.save()
        return JsonResponse({"ok": True, "session_key": request.session.session_key, "require_password_change": False})

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
    try:
        profile = user.profile
        profile.presence_status = "online"
        profile.presence_updated_at = timezone.now()
        profile.save(update_fields=["presence_status", "presence_updated_at"])
    except Exception:
        pass
    if remember:
        request.session.set_expiry(60 * 60 * 24 * 30)
    else:
        request.session.set_expiry(0)
    if not request.session.session_key:
        request.session.save()
    return JsonResponse(
        {
            "ok": True,
            "session_key": request.session.session_key,
            "require_password_change": bool(getattr(profile, "force_password_change", False)),
        }
    )


@csrf_exempt
def me_api(request):
    user = _resolve_request_user(request)

    # 🔥 redirect 절대 발생 금지
    if not user:
        return JsonResponse(
            {"error": "not_authenticated"},
            status=401
        )

    # 접속 확인 시 상태를 항상 접속중으로 동기화
    _mark_online_if_possible(user)

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
                    "work_start_hour": 9,
                    "profile_image_url": "",
                    "presence_status": "online",
                    "presence_updated_at": timezone.now(),
                    "force_password_change": False,
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
            "hire_date": getattr(p, "hire_date", None),
            "phone": p.phone,
            "position": p.position,
            "is_approved": p.is_approved,
            "work_start_hour": getattr(p, "work_start_hour", 9),
            "profile_image_url": _build_profile_image_url(request, p),
            "presence_status": getattr(p, "presence_status", "offline") or "offline",
            "presence_updated_at": getattr(p, "presence_updated_at", None),
            "force_password_change": bool(getattr(p, "force_password_change", False)),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def me_password_change_api(request):
    if request.method not in {"POST", "PATCH"}:
        return JsonResponse({"error": "method not allowed"}, status=405)

    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        profile = user.profile
    except Exception:
        return JsonResponse({"error": "profile_missing"}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    current_password = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")

    if not new_password:
        return JsonResponse({"error": "new_password_required"}, status=400)

    if new_password == current_password:
        return JsonResponse({"error": "new_password_same_as_current"}, status=400)

    must_change = bool(getattr(profile, "force_password_change", False))
    if not must_change and not user.check_password(current_password):
        return JsonResponse({"error": "invalid_current_password"}, status=400)

    user.set_password(new_password)
    user.save(update_fields=["password"])

    profile.force_password_change = False
    profile.save(update_fields=["force_password_change"])

    # Keep current session valid after password reset.
    login(request, user)
    if not request.session.session_key:
        request.session.save()

    return JsonResponse(
        {
            "ok": True,
            "session_key": request.session.session_key,
            "force_password_change": False,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def me_profile_image_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        profile = user.profile
    except Exception:
        return JsonResponse({"error": "profile_missing"}, status=403)

    uploaded = request.FILES.get("profile_image")
    if not uploaded:
        return JsonResponse({"error": "profile_image required"}, status=400)

    content_type = str(getattr(uploaded, "content_type", "") or "").lower()
    if content_type and not content_type.startswith("image/"):
        return JsonResponse({"error": "invalid image type"}, status=400)

    profile.profile_image = uploaded
    profile.save(update_fields=["profile_image"])

    return JsonResponse(
        {
            "ok": True,
            "profile_image_url": _build_profile_image_url(request, profile),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def me_presence_api(request):
    if request.method not in {"POST", "PATCH"}:
        return JsonResponse({"error": "method not allowed"}, status=405)

    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        profile = user.profile
    except Exception:
        return JsonResponse({"error": "profile_missing"}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    status_value = _normalize_presence_status(payload.get("presence_status"))
    if not status_value:
        return JsonResponse({"error": "invalid presence_status"}, status=400)

    profile.presence_status = status_value
    profile.presence_updated_at = timezone.now()
    profile.save(update_fields=["presence_status", "presence_updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "presence_status": profile.presence_status,
            "presence_updated_at": profile.presence_updated_at,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def logout_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    user = _resolve_request_user(request)
    if user:
        try:
            profile = user.profile
            profile.presence_status = "offline"
            profile.presence_updated_at = timezone.now()
            profile.save(update_fields=["presence_status", "presence_updated_at"])
        except Exception:
            pass
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
    hire_date = data.get("hire_date")
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
            hire_date=hire_date or None,
            phone=phone,
        )

    return JsonResponse({"ok": True})


@csrf_exempt
def users_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"}, status=405)

    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    q = (request.GET.get("q") or "").strip().lower()
    qs = User.objects.filter(is_active=True).select_related("profile").order_by("username")
    rows = []
    for u in qs:
        profile = getattr(u, "profile", None)
        name = getattr(profile, "name", None) or u.get_full_name() or u.username
        position = getattr(profile, "position", None) or ("admin" if u.is_superuser else "")
        item = {
            "id": u.id,
            "username": u.username,
            "name": name,
            "position": position,
            "email": u.email,
            "hire_date": getattr(profile, "hire_date", None),
            "work_start_hour": getattr(profile, "work_start_hour", 9),
            "presence_status": getattr(profile, "presence_status", "offline") if profile else "offline",
            "presence_updated_at": getattr(profile, "presence_updated_at", None) if profile else None,
        }
        if q:
            hay = f"{item['name']} {item['username']} {item['position']}".lower()
            if q not in hay:
                continue
        rows.append(item)

    return JsonResponse({"count": len(rows), "results": rows}, json_dumps_params={"ensure_ascii": False})




