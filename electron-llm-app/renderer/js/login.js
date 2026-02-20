console.log("?? login.js loaded"); // 디버깅용 로그

const KEY_REMEMBER = "remember_login";
const KEY_SESSION = "session_key";
let isSubmitting = false;

window.addEventListener("DOMContentLoaded", async () => {
  const saved = localStorage.getItem(KEY_REMEMBER) === "true";
  const rememberEl = document.getElementById("rememberLogin");
  if (rememberEl) rememberEl.checked = saved;

  const form = document.getElementById("loginForm");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      login();
    });
  }

  initLoginClock();

  if (!saved) return;

  try {
    const storedSession = localStorage.getItem(KEY_SESSION);
    if (storedSession && window.api?.setSessionKey) {
      await window.api.setSessionKey(storedSession);
    }
    const me = await window.api.getMe();
    if (me?.force_password_change) {
      const changed = await forceChangePasswordFlow("");
      if (!changed) return;
    }
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

// ?? 로딩 상태 관리
function setLoading(loading) {
  document.querySelectorAll("input, button").forEach((el) => {
    el.disabled = loading;
  });
}

// ?? 메시지 표시 (alert ?)
function showMessage(text, isError = true) {
  const msg = document.getElementById("message");
  if (!msg) return;

  msg.innerText = text;
  msg.className = isError ? "msg error" : "msg success";
}

// ? 로그인
async function login() {
  if (isSubmitting) return; // ?? 중복 방지
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
    const remember = document.getElementById("rememberLogin")?.checked;
    const data = await window.api.login(username, password, remember);
    if (remember) {
      localStorage.setItem(KEY_REMEMBER, "true");
      if (data?.session_key) localStorage.setItem(KEY_SESSION, data.session_key);
    } else {
      localStorage.removeItem(KEY_REMEMBER);
      localStorage.removeItem(KEY_SESSION);
    }

    if (data?.require_password_change) {
      const changed = await forceChangePasswordFlow(password);
      if (!changed) return;
    }
    window.nav.go("my_dashboard");

  } catch (e) {
    console.error("? login error", e);
    showMessage("관리자 승인 후 로그인 가능합니다.");

    // ?? 포커스 복구
    setTimeout(() => {
      usernameEl.focus();
    }, 0);

  } finally {
    setLoading(false);
    isSubmitting = false;
  }
}

async function forceChangePasswordFlow(currentPassword) {
  while (true) {
    const next = window.prompt("임시 비밀번호입니다. 새 비밀번호를 입력하세요.");
    if (next === null) {
      showMessage("비밀번호 변경 후 이용 가능합니다.");
      try {
        await window.api.logout();
      } catch (_e) {}
      return false;
    }
    const newPassword = String(next || "").trim();
    if (!newPassword) {
      showMessage("새 비밀번호를 입력하세요.");
      continue;
    }
    if (currentPassword && newPassword === currentPassword) {
      showMessage("기존 비밀번호와 다른 값으로 입력하세요.");
      continue;
    }
    const confirmValue = window.prompt("새 비밀번호를 다시 입력하세요.");
    if (confirmValue === null) {
      showMessage("비밀번호 변경 후 이용 가능합니다.");
      try {
        await window.api.logout();
      } catch (_e) {}
      return false;
    }
    if (newPassword !== String(confirmValue || "").trim()) {
      showMessage("비밀번호 확인이 일치하지 않습니다.");
      continue;
    }
    try {
      const changed = await window.api.changePassword(currentPassword || "", newPassword);
      if (changed?.session_key) localStorage.setItem(KEY_SESSION, changed.session_key);
      showMessage("비밀번호가 변경되었습니다.", false);
      return true;
    } catch (e) {
      console.error("password change failed", e);
      showMessage("비밀번호 변경에 실패했습니다. 다시 시도해 주세요.");
    }
  }
}

// ? Enter 키 로그인 (중복 방지 포함)
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
