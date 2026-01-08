window.openProfileInfo = async function () {
  const me = await window.api.getMe();

  document.getElementById("infoName").innerText =
    me.name || "-";

  document.getElementById("infoEmail").innerText =
    me.email || "-";

  document.getElementById("infoPhone").innerText =
    me.phone || "-";

  document.getElementById("infoBirth").innerText =
    me.birth_date || "-";

  // 메뉴 팝업 닫기
  document.getElementById("profilePopup").classList.add("hidden");

  // 기본 정보 팝업 열기
  document.getElementById("profileInfoModal").classList.remove("hidden");
};

window.closeProfileInfo = function () {
  document.getElementById("profileInfoModal").classList.add("hidden");
};