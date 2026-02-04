/* ================================
   디렉토리 토글
================================ */
function toggleNav(el) {
  const group = el.closest(".nav-group");
  if (!group) return;

  // 다른 그룹 닫기 (시스템 UX)
  document.querySelectorAll(".nav-group").forEach(g => {
    if (g !== group) g.classList.remove("open");
  });

  group.classList.toggle("open");
}

/* ================================
   현재 페이지 active 처리
================================ */
function applySidebarActiveState() {
  const current = document.body.dataset.nav; // ex: clinic
  if (current) {
    document.querySelectorAll(".nav-sub a").forEach(a => {
      if (a.dataset.nav === current) {
        a.classList.add("active");

        const group = a.closest(".nav-group");
        if (group) group.classList.add("open");
      }
    });
  }
}

let sidebarCurrentRole = "";

function normalizeRole(me) {
  const raw = String(
    me?.position ?? me?.role ?? me?.position_code ?? me?.position_key ?? ""
  )
    .trim()
    .toLowerCase();
  const map = {
    admin: "admin",
    ceo: "ceo",
    manager: "manager",
    leader: "leader",
    "계정": "admin",
    "관리자": "admin",
    "대표": "ceo",
    "대표이사": "ceo",
    "매니저": "manager",
    "팀장": "leader",
  };
  return map[raw] || raw;
}

async function applySidebarRoleAccess() {
  const roleOnlyLinks = document.querySelectorAll(".nav-sub a[data-role-only]");
  if (!roleOnlyLinks.length) return;

  let myRole = "";
  try {
    const me = await window.api?.getMe?.();
    myRole = normalizeRole(me);
  } catch (e) {
    myRole = "";
  }
  sidebarCurrentRole = myRole;

  roleOnlyLinks.forEach((link) => {
    const allow = String(link.dataset.roleOnly || "")
      .split(",")
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean);

    const visible = allow.includes(myRole);
    link.classList.toggle("hidden", !visible);
  });
}

async function openKakaoWorkShortcut() {
  if (window.nav?.openKakaoWork) {
    try {
      await window.nav.openKakaoWork();
      return;
    } catch (e) {
      window.showAlert?.("카카오워크 앱 실행에 실패했습니다.");
      return;
    }
  }
  window.showAlert?.("카카오워크 앱 실행 기능을 사용할 수 없습니다.");
}

/* ================================
   Notion Shortcut (추가)
================================ */
function openNotionShortcut() {
  if (window.nav?.openNotion) {
    try {
      window.nav.openNotion();
      return;
    } catch (e) {
      window.showAlert?.("노션 실행에 실패했습니다.");
      return;
    }
  }
  window.showAlert?.("노션 앱 실행 기능을 사용할 수 없습니다.");
}

/* ================================
   Sidebar Shortcut Click (이벤트 위임)
================================ */
// Sidebar는 동적 로드(loadLayout)라서 이벤트 위임으로 클릭을 안정적으로 처리.
document.addEventListener("click", async (e) => {
  const kakaoBtn = e.target?.closest?.("#kakaoWorkShortcut");
  if (kakaoBtn) {
    e.preventDefault();
    openKakaoWorkShortcut();
    return;
  }

  const notionBtn = e.target?.closest?.("#notionShortcut");
  if (notionBtn) {
    e.preventDefault();
    openNotionShortcut();
    return;
  }

  const restrictedLink = e.target?.closest?.(".nav-sub a[data-role-only]");
  if (restrictedLink) {
    const allow = String(restrictedLink.dataset.roleOnly || "")
      .split(",")
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean);

    let role = sidebarCurrentRole;
    if (!role) {
      try {
        const me = await window.api?.getMe?.();
        role = normalizeRole(me);
        sidebarCurrentRole = role;
      } catch (err) {
        role = "";
      }
    }

    // 역할을 아직 판별 못한 경우엔 여기서 차단하지 않고 app.js 접근제어로 위임
    if (role && !allow.includes(role)) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof window.showAccessDenied === "function") window.showAccessDenied();
      else window.showAlert?.("접근 불가");
    }
  }
});


/* ================================
   브랜드 이동
================================ */
function goDashboard() {
  location.href = "my_dashboard.html";
}

async function buildSidebarAuthHeaders() {
  const headers = {};
  try {
    const sessionKey = await window.session?.getKey?.();
    if (sessionKey) headers["X-Sessionid"] = sessionKey;
  } catch (e) {
    // ignore
  }
  return headers;
}

async function refreshSidebarNotificationBadge() {
  const badge = document.getElementById("sidebarNotifyBadge");
  if (!badge) return;
  try {
    const headers = await buildSidebarAuthHeaders();
    const base = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";
    const res = await fetch(`${base}/api/data/notifications/?limit=1`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) return;
    const data = await res.json();
    let unread = Number(data?.unread_count || 0);
    try {
      const mres = await fetch(`${base}/api/data/messages/?box=inbox&limit=1`, {
        credentials: "include",
        headers,
      });
      if (mres.ok) {
        const mdata = await mres.json();
        unread += Number(mdata?.unread_count || 0);
      }
    } catch (e) {
      // ignore
    }
    if (unread > 0) {
      badge.classList.remove("hidden");
      badge.textContent = unread > 99 ? "99+" : String(unread);
    } else {
      badge.classList.add("hidden");
    }
  } catch (e) {
    // ignore network/auth errors for sidebar badge
  }
}

function initSidebarNotifyBadge() {
  refreshSidebarNotificationBadge();
  setInterval(refreshSidebarNotificationBadge, 30000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    applySidebarRoleAccess();
    applySidebarActiveState();
    initSidebarNotifyBadge();
  });
} else {
  applySidebarRoleAccess();
  applySidebarActiveState();
  initSidebarNotifyBadge();
}
