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
  // 🔥 Electron에서도 query 유지되게 강제
  window.location.href =
    `clinic_guide.html?clinic_id=${encodeURIComponent(clinicId)}`;
}

// ================================
// 업체 데이터 (HTML에서 전부 이관)
// ================================
const clinics = [
  // 산부인과
  {id: 8, name: "봄빛 병원", type: "산부인과", typeClass: "type-ob", logo: "bombit.jpg" },
  {id: 25, name: "이쁜여성의원", type: "산부인과", typeClass: "type-ob", logo: "이쁜여성의원.jpg" },
  {id: 26, name: "여노피 <br>산부인과", type: "산부인과", typeClass: "type-ob", logo: "여노피.jpg" },

  // 성형외과
  {id: 9, name: "원트 성형외과", type: "성형외과", typeClass: "type-ps", logo: "원트.jpg" },
  {id: 7, name: "윈느 성형외과", type: "성형외과", typeClass: "type-ps", logo: "윈느.jpg" },
  {id: 12, name: "신상 성형외과", type: "성형외과", typeClass: "type-ps", logo: "신상.jpg" },
  {id: 10, name: "밸런스랩 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "밸런스랩.jpg" },
  {id: 19, name: "밸런스랩 <br> A&A", type: "성형외과", typeClass: "type-ps", logo: "A&A.jpg" },
  {id: 11, name: "히트 성형외과", type: "성형외과", typeClass: "type-ps", logo: "히트.jpg" },
  {id: 15, name: "다름 성형외과", type: "성형외과", typeClass: "type-ps", logo: "다름.jpg" },
  {id: 14, name: "지힐링스퀘어", type: "성형외과", typeClass: "type-ps", logo: "지힐링.jpg" },
  {id: 16, name: "아우어 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "아우어.jpg" },
  {id: 17, name: "강남12의원", type: "성형외과", typeClass: "type-ps", logo: "강남12.jpg" },
  {id: 18, name: "프리마 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "프리마.jpg" },
  {id: 1, name: "서진 성형외과", type: "성형외과", typeClass: "type-ps", logo: "서진.jpg" },
  {id: 21, name: "라라 성형외과", type: "성형외과", typeClass: "type-ps", logo: "라라.jpg" },

  // 피부과
  {id: 22, name: "사치바이오", type: "피부과", typeClass: "type-derma", logo: "사치바이오.jpg" },
  {id: 23, name: "PHD피부과", type: "피부과", typeClass: "type-derma", logo: "PHD.jpg" },
  {id: 24, name: "리프톤 피부과", type: "피부과", typeClass: "type-derma", logo: "리프톤.jpg" },
];

// ================================
// 카드 렌더링
// ================================
function renderClinics(list) {
  const grid = document.getElementById("clinicGrid");
  if (!grid) return;

  grid.innerHTML = "";

  list.forEach((c) => {
    const card = document.createElement("div");
    card.className = "clinic-card";

    card.innerHTML = `
      <div class="clinic-top">
        <div class="clinic-logo">
          <img
            src="assets/logos/${c.logo}"
            alt="${c.name} 로고"
            onerror="this.src='assets/logos/default.png'"
          />
        </div>

        <div class="clinic-name">${c.name}</div>
        <div class="clinic-type ${c.typeClass}">${c.type}</div>
      </div>

      <div class="clinic-actions">
        <button class="btn btn-primary sm" onclick="goReview()">리뷰 생성</button>
        <button class="btn sm" onclick="goClinicGuide('${c.id}')">가이드</button>
        <button class="btn ghost sm">작업</button>
      </div>
    `;

    grid.appendChild(card);
  });
}

function filterClinicsByQuery(q) {
  const filtered = clinics.filter(c =>
    c.name.toLowerCase().includes(q)
  );
  renderClinics(filtered);
}

const globalSearchIndex = {
  pages: [
    { key: "대시보드", page: "dashboard" },
    { key: "리뷰", page: "review" },
    { key: "리뷰 생성", page: "review" },
    { key: "병원 가이드", page: "clinic_guide" },
    { key: "가이드", page: "clinic_guide" },
  ],
};

// ================================
// 초기 실행
// ================================
document.addEventListener("DOMContentLoaded", () => {
  renderClinics(clinics);
});

// ================================
// 전역 바인딩
// ================================
window.goReview = goReview;
window.goClinicGuide = goClinicGuide;
window.filterClinicsByQuery = filterClinicsByQuery;
