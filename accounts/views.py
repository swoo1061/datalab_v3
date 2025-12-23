from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User

# Create your views here.


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('/dashboard/')
        else:
            messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")

    return render(request, "accounts/login.html")


def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')

def signup_view(request):
    if request.method == 'POST':
        User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password1']
        )
        return redirect('accounts:login')
    return render(request, 'accounts/signup.html')