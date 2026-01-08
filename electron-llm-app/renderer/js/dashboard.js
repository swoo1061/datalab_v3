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

function goClinicGuide() {
  navigate("clinic");
}

// ================================
// 전역 바인딩
// ================================
window.goReview = goReview;
window.goClinicGuide = goClinicGuide;
