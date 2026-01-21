const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";
let position = null;

// 🔥 DOM 로드 후 실행 (중요)
document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll(".position-btn");

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      // active 토글
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      position = btn.dataset.value;
      console.log("선택된 직급:", position); // 디버깅용 로그
    });
  });
});

// 회원가입
async function signup() {
  const payload = {
    name: document.getElementById("name").value.trim(),
    birth_date: document.getElementById("birthDate").value.trim(), // ✅ 수정
    phone: document.getElementById("phone").value.trim(),
    email: document.getElementById("email").value.trim(),
    username: document.getElementById("username").value.trim(),
    password: document.getElementById("password").value.trim(),
    position,
  };

  console.log("SIGNUP PAYLOAD:", payload); // 디버깅용 로그

  if (!payload.name || !payload.email || !payload.username || !payload.password) {
    alert("모든 항목을 입력하세요.");
    return;
  }

  if (!payload.position) {
    alert("직급을 선택하세요.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/accounts/signup/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "회원가입 실패");
      return;
    }

    document.getElementById("message").innerText =
      "회원가입 완료! 관리자 승인 후 로그인 가능합니다.";

    setTimeout(() => {
      window.nav.go("login");
        }, 1500); // ⏱ 1.5초 후 로그인 화면 이동

  } catch (e) {
    console.error(e); // 디버깅용 로그
    alert("회원가입 중 오류 발생");
  }
}

// 로그인 페이지로 이동
function goLogin() {
  window.nav.go("login");
}

// 🔥 전역 바인딩 (Electron 필수)
window.signup = signup;
window.goLogin = goLogin;
