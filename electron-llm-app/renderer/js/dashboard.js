console.log("dashboard.js loaded");

// ================================
// 이동 유틸
// ================================
function navigate(page) {
  if (window.nav?.go) window.nav.go(page);
  else window.location.href = `${page}.html`;
}

function goReview() {
  navigate("review");
}

function goClinicGuide(clinicId) {
  navigate(`clinic_guide?clinic_id=${encodeURIComponent(clinicId)}`);
}

function goClinicPage(clinicId) {
  if (clinicId) {
    localStorage.setItem("lastClinicId", String(clinicId));
  }
  window.location.href = `clinic_page.html?clinic_id=${encodeURIComponent(clinicId)}`;
}



// ================================
// 즐겨찾기 (서버 연동)
// ================================
let favoriteClinicIds = [];

async function loadFavorites() {
  const list = await window.api.getFavorites();
  favoriteClinicIds = (list || []).map(f => Number(f.clinic_id));
}

/* 즐겨찾기 토글 */
async function toggleFavorite(e, clinicId) {
  e.stopPropagation();
  const id = Number(clinicId);

  try {
    if (favoriteClinicIds.includes(id)) {
      await window.api.removeFavorite(id);
    } else {
      await window.api.addFavorite(id);
    }
  } catch (e) {
    window.showAlert?.("즐겨찾기 저장 실패");
    return;
  }

  await drawDashboard();
}

/* 대시보드 렌더 */
async function drawDashboard() {
  await loadFavorites();

  const viewData = clinics.map(c => ({
    ...c,
    isFavorite: favoriteClinicIds.includes(Number(c.id)),
  }));

  renderClinics(viewData, "clinicGrid");
}

async function initDashboardPage() {
  if (window.__dashboardPageInitialized) return;
  window.__dashboardPageInitialized = true;
  await loadFavorites();
  drawDashboard();
}

// ================================
// (기존) 로컬 즐겨찾기 - 유지하되 실제로는 안 씀
// ================================
const favoriteClinics = new Set(); // 임시 (나중에 서버 연동)
function toggleFavoriteLocalOnly(e, clinicName) {
  e.stopPropagation();

  const btn = e.currentTarget;

  if (favoriteClinics.has(clinicName)) {
    favoriteClinics.delete(clinicName);
    btn.classList.remove("active");
    btn.innerText = "☆";
  } else {
    favoriteClinics.add(clinicName);
    btn.classList.add("active");
    btn.innerText = "★";
  }

  console.log("⭐ (로컬) 즐겨찾기 목록:", [...favoriteClinics]);
}


function filterClinicsByQuery(q) {
  const qq = (q || "").toLowerCase();
  const filtered = clinics.filter((c) => c.name.toLowerCase().includes(qq));
  renderClinics(filtered);
}

// (기존) 글로벌 검색 인덱스 - 유지
const globalSearchIndex = {
  pages: [
    { key: "업체 대시보드", page: "dashboard" },
    { key: "리뷰", page: "review" },
    { key: "리뷰 생성", page: "review" },
    { key: "병원 가이드", page: "clinic_guide" },
    { key: "가이드", page: "clinic_guide" },
  ],
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initDashboardPage();
  }, { once: true });
} else {
  initDashboardPage();
}

// ================================
// 전역 바인딩
// ================================
window.goReview = goReview;
window.goClinicGuide = goClinicGuide;
window.goClinicPage = goClinicPage;
window.filterClinicsByQuery = filterClinicsByQuery;

// ✅ 즐겨찾기 함수는 서버 연동 버전이 전역으로 살아야 함
window.toggleFavorite = toggleFavorite;

// (기존) 로컬도 남김(원하면 테스트용으로 호출 가능)
window.toggleFavoriteLocalOnly = toggleFavoriteLocalOnly;
