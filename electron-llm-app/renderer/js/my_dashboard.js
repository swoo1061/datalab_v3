console.log("my_dashboard.js loaded");

// ================================
// (기존) 로컬 즐겨찾기 - 유지
// ================================
function getCurrentUserId() {
  return "user_demo"; // 공용과 동일(기존 유지)
}

function getFavorites() {
  const key = `favoriteClinics::${getCurrentUserId()}`;
  return JSON.parse(localStorage.getItem(key) || "[]");
}

// ================================
// ✅ 서버 즐겨찾기 기반 “나의 대시보드”
// ================================
async function getFavoritesFromServer() {
  try {
    const list = await window.api.getFavorites();
    return (list || []).map((f) => Number(f.clinic_id));
  } catch (e) {
    console.warn("getFavoritesFromServer failed", e);
    return [];
  }
}

async function renderMyDashboard() {
  const gridId = "myClinicGrid";

  try {
    // 1️⃣ 서버에서 즐겨찾기 ID 목록
    const favorites = await window.api.getFavorites();
    const favoriteIds = favorites.map(f => Number(f.clinic_id));

    if (favoriteIds.length === 0) {
      document.getElementById(gridId).innerHTML =
        `<p class="muted">즐겨찾기한 병원이 없습니다.</p>`;
      return;
    }

    // 2️⃣ 공용 clinics에서 필터링
    const myClinics = clinics
      .filter(c => favoriteIds.includes(Number(c.id)))
      .map(c => ({
        ...c,
        isFavorite: true, // 개인 대시보드는 전부 즐겨찾기
      }));

    // 3️⃣ 공용 카드 그대로 렌더
    renderClinics(myClinics, gridId);

  } catch (e) {
    console.error("❌ 내 대시보드 로드 실패", e);
  }
}

document.addEventListener("DOMContentLoaded", renderMyDashboard);