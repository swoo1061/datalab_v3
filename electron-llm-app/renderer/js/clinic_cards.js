console.log("clinic_cards.js loaded");

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
  navigate(`clinic_page?clinic_id=${encodeURIComponent(clinicId)}`);
}

/**
 * 병원 카드 렌더링 (공용)
 * @param {Array} list - clinic list
 * @param {String} gridId - 렌더링할 컨테이너 ID
 */
function renderClinics(list, gridId = "clinicGrid") {
  const grid = document.getElementById(gridId);
  if (!grid) return;

  grid.innerHTML = "";

  list.forEach((c) => {
    const card = document.createElement("div");
    card.className = "clinic-card";

    card.innerHTML = `
      <div class="clinic-top">

        <!-- ⭐ 즐겨찾기 -->
        <button
          class="favorite-btn ${c.isFavorite ? "active" : ""}"
          title="즐겨찾기"
          onclick="toggleFavorite(event, ${c.id})"
        >
          ${c.isFavorite ? "★" : "☆"}
        </button>

        <!-- 🏷️ 뱃지 -->
        <div class="clinic-type ${c.typeClass}">
          ${c.type}
        </div>

        <!-- 로고 -->
        <div class="clinic-logo">
          <img
            src="assets/logos/${c.logo || "default.png"}"
            alt="${c.name}"
            onerror="this.src='assets/logos/default.png'"
          />
        </div>

        <!-- 이름 -->
        <div class="clinic-name">${c.name}</div>
      </div>

      <div class="clinic-actions">
        <button class="btn btn-primary sm" onclick="goReview()">리뷰 생성</button>
        <button class="btn sm" onclick="goClinicGuide(${c.id})">가이드</button>
        <button class="btn ghost sm" onclick="goClinicPage(${c.id})">업무</button>
      </div>
    `;

    grid.appendChild(card);
  });
}

// 전역 노출
window.renderClinics = renderClinics;
