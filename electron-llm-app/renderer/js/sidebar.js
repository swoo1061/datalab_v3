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
document.addEventListener("DOMContentLoaded", () => {
  const current = document.body.dataset.nav; // ex: clinic
  if (!current) return;

  document.querySelectorAll(".nav-sub a").forEach(a => {
    if (a.dataset.nav === current) {
      a.classList.add("active");

      const group = a.closest(".nav-group");
      if (group) group.classList.add("open");
    }
  });
});

/* ================================
   브랜드 이동
================================ */
function goDashboard() {
  location.href = "dashboard.html";
}
