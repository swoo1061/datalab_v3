// js/app.js

async function loadComponent(targetId, url) {
  const root = document.getElementById(targetId);
  if (!root) {
    console.warn(`❗ target not found: ${targetId}`);
    return;
  }

  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} fetch failed`);
  root.innerHTML = await res.text();
}

function setActiveNav(key) {
  document.querySelectorAll(".sidebar .nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.nav === key);
  });
}

function navigate(page) {
  if (window.nav?.go) {
    window.nav.go(page); // Electron
  } else {
    window.location.href = `${page}.html`; // Web
  }
}

async function loadLayout() {
  // header는 header.js에서 처리하므로 여기선 sidebar만
  await loadComponent("appSidebar", "./components/sidebar.html");
}

function goMyDashboard() {
  window.location.href = "my_dashboard.html";
}

window.navigate = navigate;
window.loadLayout = loadLayout;

// Fallback: unblock inputs if a full-screen fixed layer gets stuck.
function releaseBlockingLayers() {
  const allow = new Set([
    "app-header-slot",
    "app-sidebar-slot",
    "modal-panel",
    "modal-content",
    "profile-popup",
    "profile-info-modal",
  ]);

  document.querySelectorAll("body *").forEach((el) => {
    const style = getComputedStyle(el);
    if (style.position !== "fixed") return;

    const rect = el.getBoundingClientRect();
    const covers =
      rect.width >= window.innerWidth - 2 &&
      rect.height >= window.innerHeight - 2;

    if (!covers) return;
    if ([...el.classList].some((c) => allow.has(c))) return;

    if (el.classList.contains("modal") || el.classList.contains("modal-backdrop")) {
      el.classList.add("hidden");
    }

    el.style.pointerEvents = "none";
  });

  document.querySelectorAll("input, select, textarea").forEach((el) => {
    el.disabled = false;
    el.style.pointerEvents = "auto";
  });
}

setInterval(releaseBlockingLayers, 500);
