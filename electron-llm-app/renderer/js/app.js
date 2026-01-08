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

window.navigate = navigate;
window.loadLayout = loadLayout;