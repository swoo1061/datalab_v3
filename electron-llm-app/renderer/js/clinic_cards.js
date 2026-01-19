console.log("clinic_cards.js loaded");

// ================================
// 이동 유틸
// ================================
function navigate(page) {
  if (page.includes("?")) {
    const [base, query] = page.split("?");
    if (window.nav?.go) {
      window.nav.go(page).catch(() => {
        window.location.href = `${base}.html?${query}`;
      });
    } else {
      window.location.href = `${base}.html?${query}`;
    }
    return;
  }
  if (window.nav?.go) {
    window.nav.go(page);
    return;
  }
  window.location.href = `${page}.html`;
}

function goReview() {
  navigate("review");
}

function goReviewWithClinic(clinicId) {
  navigate(`review?clinic_id=${encodeURIComponent(clinicId)}`);
}

function goGangnamReviewWithClinic(clinicId) {
  navigate(`gangnam_review?clinic_id=${encodeURIComponent(clinicId)}`);
}

function goPlatformReviewWithClinic(clinicId, platform) {
  navigate(`review?clinic_id=${encodeURIComponent(clinicId)}&platform=${encodeURIComponent(platform)}`);
}

function closeAllReviewMenus() {
  document.querySelectorAll(".review-menu.open").forEach((menu) => {
    menu.classList.remove("open");
  });
}

function toggleReviewMenu(event, clinicId) {
  event.stopPropagation();
  const card = event.currentTarget.closest(".clinic-card");
  if (!card) return;
  const menu = card.querySelector(".review-menu");
  if (!menu) return;

  const isOpen = menu.classList.contains("open");
  closeAllReviewMenus();
  if (!isOpen) menu.classList.add("open");

  if (!window._reviewMenuBound) {
    document.addEventListener("click", closeAllReviewMenus);
    window._reviewMenuBound = true;
  }
}

function selectReviewOption(event, type, clinicId) {
  event.stopPropagation();
  closeAllReviewMenus();
  if (type === "ai") return goReviewWithClinic(clinicId);
  if (type === "gangnam") return goGangnamReviewWithClinic(clinicId);
  if (type === "babytok") return goPlatformReviewWithClinic(clinicId, "babytok");
  if (type === "yeoshin") return goPlatformReviewWithClinic(clinicId, "yeoshin");
}

function goClinicGuide(event, clinicId) {
  event?.stopPropagation();
  navigate(`clinic_guide?clinic_id=${encodeURIComponent(clinicId)}`);
}

function goClinicPage(event, clinicId) {
  event?.stopPropagation();
  navigate(`clinic_page?clinic_id=${encodeURIComponent(clinicId)}`);
}

function goPostsDashboard(event, clinicId) {
  event?.stopPropagation();
  navigate(`posts_dashboard?clinic_id=${encodeURIComponent(clinicId)}`);
}

function getContractKey(clinicId) {
  return `contractDate::${clinicId}`;
}

function getContractDate(clinicId) {
  return localStorage.getItem(getContractKey(clinicId)) || "";
}

function setContractDate(clinicId, value) {
  localStorage.setItem(getContractKey(clinicId), value || "");
}

function closeAllMoreMenus() {
  document.querySelectorAll(".more-menu.open").forEach((menu) => {
    menu.classList.remove("open");
  });
}

function toggleMoreMenu(event) {
  event.stopPropagation();
  const card = event.currentTarget.closest(".clinic-card");
  if (!card) return;
  const menu = card.querySelector(".more-menu");
  if (!menu) return;
  const isOpen = menu.classList.contains("open");
  closeAllMoreMenus();
  if (!isOpen) menu.classList.add("open");
  if (!window._moreMenuBound) {
    document.addEventListener("click", closeAllMoreMenus);
    window._moreMenuBound = true;
  }
}

function stripClinicSuffix(name) {
  return String(name || "")
    .replaceAll("<br>", " ")
    .replace(/(피부과|성형외과|산부인과)\s*$/g, "")
    .trim();
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
    card.addEventListener("click", (e) => {
      if (e.target.closest(".clinic-actions")) return;
      goClinicPage(null, c.id);
    });

    card.innerHTML = `
      <div class="clinic-top">

        <!-- ⭐ 즐겨찾기 -->
        <button
          class="favorite-btn ${c.isFavorite ? "active" : ""}"
          title="즐겨찾기"
          onclick="toggleFavorite(event, ${c.id}); event.stopPropagation();"
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
        <button class="btn btn-primary sm" onclick="toggleReviewMenu(event, ${c.id}); event.stopPropagation();">리뷰 생성</button>
        <div class="review-menu">
          <button class="menu-item theme-ai" onclick="selectReviewOption(event, 'ai', ${c.id})">AI 리뷰작성</button>
          <button class="menu-item theme-gangnam" onclick="selectReviewOption(event, 'gangnam', ${c.id})">강남언니</button>
          <button class="menu-item theme-babytok" onclick="selectReviewOption(event, 'babytok', ${c.id})">바비톡</button>
          <button class="menu-item theme-yeoshin" onclick="selectReviewOption(event, 'yeoshin', ${c.id})">여신티켓</button>
        </div>
        <button class="btn sm" onclick="toggleMoreMenu(event)">더보기</button>
        <div class="more-menu">
          <button class="menu-item" onclick="goClinicGuide(event, ${c.id})">${stripClinicSuffix(c.name)} 가이드</button>
          <button class="menu-item" onclick="goPostsDashboard(event, ${c.id})">게시글 관리</button>
          <div class="menu-row">
            <span>계약일</span>
            <input class="contract-input" type="date" data-clinic-id="${c.id}" />
          </div>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  bindContractInputs();
}

function bindContractInputs() {
  document.querySelectorAll(".contract-input").forEach((input) => {
    const clinicId = input.dataset.clinicId;
    if (!clinicId) return;
    input.value = getContractDate(clinicId);
    input.addEventListener("click", (e) => e.stopPropagation());
    input.addEventListener("blur", () => {
      setContractDate(clinicId, input.value);
    });
  });
}

// 전역 노출
window.renderClinics = renderClinics;
