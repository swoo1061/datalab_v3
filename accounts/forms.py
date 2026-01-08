from django import forms
from django.contrib.auth.models import User

POSITION_CHOICES = [
    ("manager", "매니저"),
    ("leader", "팀장"),
    ("ceo", "대표이사"),
]

class SignupForm(forms.Form):
    name = forms.CharField(label="이름", max_length=50)
    email = forms.EmailField(label="이메일")
    position = forms.ChoiceField(label="직급", choices=POSITION_CHOICES)

    username = forms.CharField(label="아이디", max_length=30)
    password1 = forms.CharField(
        label="비밀번호",
        widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label="비밀번호 확인",
        widget=forms.PasswordInput
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "비밀번호가 일치하지 않습니다.")
        return cleaned