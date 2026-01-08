console.log("header.js loaded"); // 디버깅용 로그

;// 직급 표시용 매핑 (DB 키 → 화면용)
const POSITION_LABEL = {
  admin: "...",
  manager: "매니저",
  leader: "팀장",
  ceo: "대표이사",
}

/* ================================
   헤더 로드
================================ */
async function loadHeader(pageTitle = "") {
  const headerRoot = document.getElementById("appHeader");
  if (!headerRoot) return;

  // 헤더 HTML 로드 (중복 방지)
  if (headerRoot.children.length === 0) {
    const res = await fetch("./components/header.html");
    if (!res.ok) {
      console.error("header.html fetch failed"); // 디버깅용 로그
      return;
    }
    headerRoot.innerHTML = await res.text();
  }

  // 페이지 타이틀
  const titleEl = document.getElementById("pageTitle");
  if (titleEl) titleEl.innerText = pageTitle;

  // 유저 정보
  let me;
    try {
      me = await window.api.getMe();
    } catch (e) {
      console.warn("Not logged in"); // 디버깅용 로그
      window.nav.go("login");
      return;
    }

    if (me.error === "not_authenticated") {
      window.nav.go("login");
      return;
    }

  const name = me?.name || me?.username || "사용자";
  const rawPosition = me?.position || "";
  const position = POSITION_LABEL[rawPosition] || rawPosition;
  const email = me?.email || "";

  // 헤더 표시
  const userNameEl = document.getElementById("userName");
  if (userNameEl) {
    userNameEl.innerText = position
      ? `${name} ${position}`
      : name;
  }

  // 팝업 정보
  const profileNameEl = document.getElementById("profileName");
  const profilePositionEl = document.getElementById("profilePosition");
  const profileEmailEl = document.getElementById("profileEmail");

  if (profileNameEl) profileNameEl.innerText = name;
  if (profilePositionEl) profilePositionEl.innerText = position;
  if (profileEmailEl) profileEmailEl.innerText = email;

  // 이벤트 바인딩
  document
    .getElementById("userChip")
    ?.addEventListener("click", toggleProfile);

  bindProfileMenu();
}

/* ================================
   프로필 토글
================================ */
function toggleProfile() {
  const popup = document.getElementById("profilePopup");
  if (popup) popup.classList.toggle("hidden");
}

/* ================================
   프로필 메뉴
================================ */
function bindProfileMenu() {
  document.querySelectorAll(".menu-item").forEach(item => {
    item.onclick = async () => {
      const action = item.dataset.action;
      console.log("PROFILE MENU:", action); // 디버깅용 로그

      if (action === "profile") {
        openProfileInfo();
      }

      if (action === "attendance") {
        alert("출퇴근 기록 준비중");
      }

      if (action === "my-dashboard") {
        window.nav.go("dashboard");
      }
    };
  });
}

/* ================================
   로그아웃
================================ */
async function logout() {
  try {
    await window.api.logout();
  } catch (e) {
    console.error("logout failed", e); // 디버깅용 로그
  }
  window.nav.go("login");
}

async function openProfileInfo() {
  let me;
  try {
    me = await window.api.getMe();
  } catch (e) {
    console.error("getMe failed", e);
    return;
  }

  // 값 채우기
  document.getElementById("infoName").innerText =
    me.name || "-";

  document.getElementById("infoEmail").innerText =
    me.email || "-";

  document.getElementById("infoPhone").innerText =
    me.phone || "-";

  document.getElementById("infoBirth").innerText =
    me.birth_date || "-";

  // 기존 프로필 팝업 닫기
  document.getElementById("profilePopup")?.classList.add("hidden");

  // 기본 정보 팝업 열기
  document.getElementById("profileInfoModal")?.classList.remove("hidden");
}

function closeProfileInfo() {
  document.getElementById("profileInfoModal")?.classList.add("hidden");
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;

  const modal = document.getElementById("profileInfoModal");
  if (!modal) return;

  // 팝업이 열려 있을 때만 닫기
  if (!modal.classList.contains("hidden")) {
    closeProfileInfo();
  }
});

/* ================================
   전역 바인딩
================================ */
window.loadHeader = loadHeader;
window.toggleProfile = toggleProfile;
window.logout = logout;
window.openProfileInfo = openProfileInfo;
window.closeProfileInfo = closeProfileInfo;
