console.log("🔥 login.js loaded"); // 디버깅용 로그

const KEY_REMEMBER = "remember_login";
let isSubmitting = false;

window.addEventListener("DOMContentLoaded", async () => {
  const saved = localStorage.getItem(KEY_REMEMBER) === "true";
  const rememberEl = document.getElementById("rememberLogin");
  if (rememberEl) rememberEl.checked = saved;

  initLoginClock();

  if (!saved) return;

  try {
    await window.api.getMe();
    window.nav.go("my_dashboard");
  } catch {}
});

function initLoginClock() {
  const timeEl = document.getElementById("loginTime");
  const dateEl = document.getElementById("loginDate");
  if (!timeEl || !dateEl) return;

  const update = () => {
    const now = new Date();
    timeEl.innerText = now.toLocaleTimeString("ko-KR", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    dateEl.innerText = now.toLocaleDateString("ko-KR", {
      month: "long",
      day: "numeric",
      weekday: "short",
    });
  };

  update();
  setInterval(update, 1000);
}

// 🔒 로딩 상태 관리
function setLoading(loading) {
  document.querySelectorAll("input, button").forEach(el => {
    el.disabled = loading;
  });
}

// 🔔 메시지 표시 (alert ❌)
function showMessage(text, isError = true) {
  const msg = document.getElementById("message");
  if (!msg) return;

  msg.innerText = text;
  msg.className = isError ? "msg error" : "msg success";
}

// ✅ 로그인
async function login() {
  if (isSubmitting) return; // 🔥 중복 방지
  isSubmitting = true;

  const usernameEl = document.getElementById("username");
  const passwordEl = document.getElementById("password");

  const username = usernameEl.value.trim();
  const password = passwordEl.value.trim();

  if (!username || !password) {
    showMessage("아이디와 비밀번호를 입력하세요.");
    isSubmitting = false;
    return;
  }

  setLoading(true);
  showMessage("");

  try {
    await window.api.login(username, password);

    const remember = document.getElementById("rememberLogin")?.checked;
    if (remember) localStorage.setItem(KEY_REMEMBER, "true");
    else localStorage.removeItem(KEY_REMEMBER);

    window.nav.go("my_dashboard");

  } catch (e) {
    console.error("❌ login error", e);
    showMessage("관리자 승인 후 로그인 가능합니다.");

    // 🔥 포커스 복구
    setTimeout(() => {
      usernameEl.focus();
    }, 0);

  } finally {
    setLoading(false);
    isSubmitting = false;
  }
}

// ✅ Enter 키 로그인 (중복 방지 포함)
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    login();
  }
});

function goSignup() {
  window.nav.go("signup");
}

function quitApp() {
  window.api?.quitApp?.();
}

window.login = login;
window.goSignup = goSignup;
window.quitApp = quitApp;
