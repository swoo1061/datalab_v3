from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import SignupForm
from .models import UserProfile
from apps.data.permissions import can_access_web_dashboard

# Create your views here.


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 1️⃣ 아이디 존재 여부 먼저 확인
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
            return redirect("accounts:login")

        # 2️⃣ 승인 대기 체크
        if not user_obj.is_active:
            messages.warning(request, "현재 관리자 승인 대기 중인 계정입니다.")
            return redirect("accounts:login")

        # 3️⃣ 비밀번호 인증
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
            return redirect("accounts:login")

        # 4️⃣ 로그인 성공
        login(request, user)

        profile = getattr(user, "profile", None)
        if can_access_web_dashboard(user):
            return redirect(reverse("dashboard:index"))
        return render(request, "core/forbidden.html", status=403)

    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')

def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
            )

            UserProfile.objects.create(
                user=user,
                name=form.cleaned_data["name"],
                birth_date=form.cleaned_data["birth_date"] or None,
                phone=form.cleaned_data["phone"],
                email=form.cleaned_data["email"],
                position=form.cleaned_data["position"],
                is_approved=False,  # 승인 대기
            )

            messages.success(
                request,
                "계정 신청이 완료되었습니다. 관리자 승인 후 이용 가능합니다."
            )
            return redirect("accounts:login")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def doctor_report_view(request):
    user = request.user
    if can_access_web_dashboard(user):
        return redirect("dashboard:index")
    return render(request, "core/forbidden.html", status=403)

