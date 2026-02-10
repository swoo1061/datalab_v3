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
const sidebarPermissionCache = new Map();

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
  const permissionLinks = document.querySelectorAll(".nav-sub a[data-permission]");
  if (!roleOnlyLinks.length && !permissionLinks.length) return;

  let myRole = "";
  try {
    const me = await window.api?.getMe?.();
    myRole = normalizeRole(me);
  } catch (e) {
    myRole = "";
  }
  sidebarCurrentRole = myRole;

  for (const link of roleOnlyLinks) {
    const allow = String(link.dataset.roleOnly || "")
      .split(",")
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean);
    const key = String(link.dataset.permission || "").trim();
    const roleAllowed = allow.includes(myRole);
    const permissionAllowed = key ? await fetchSidebarPermission(key) : false;
    const visible = roleAllowed || permissionAllowed;
    link.classList.toggle("hidden", !visible);
  }

  for (const link of permissionLinks) {
    if (link.dataset.roleOnly) continue;
    const key = String(link.dataset.permission || "").trim();
    if (!key) continue;
    const visible = await fetchSidebarPermission(key);
    link.classList.toggle("hidden", !visible);
  }
}

async function fetchSidebarPermission(key) {
  if (sidebarPermissionCache.has(key)) return sidebarPermissionCache.get(key);
  try {
    const headers = await buildSidebarAuthHeaders();
    const base = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";
    const res = await fetch(`${base}/api/data/system-permissions/me/?key=${encodeURIComponent(key)}`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) return false;
    const data = await res.json();
    const enabled = Boolean(data?.enabled);
    sidebarPermissionCache.set(key, enabled);
    return enabled;
  } catch (_e) {
    return false;
  }
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

    const key = String(restrictedLink.dataset.permission || "").trim();
    let permissionAllowed = false;
    if (key) {
      permissionAllowed = await fetchSidebarPermission(key);
    }

    // 역할 기반 차단 대신 role OR permission 규칙 적용
    if (role && !allow.includes(role) && !permissionAllowed) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof window.showAccessDenied === "function") window.showAccessDenied();
      else window.showAlert?.("접근 불가");
    }
  }

  const permissionLink = e.target?.closest?.(".nav-sub a[data-permission]");
  if (permissionLink) {
    const key = String(permissionLink.dataset.permission || "").trim();
    if (!key) return;
    const enabled = await fetchSidebarPermission(key);
    if (!enabled) {
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
  const badge = document.getElementById("sidebarNotifyBadge");
  if (badge) badge.classList.add("hidden");
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
