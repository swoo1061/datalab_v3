console.log("calendar_dashboard.js loaded");

const API_BASE = "http://127.0.0.1:8000";

function getMonthValue() {
  const input = document.getElementById("calendarMonth");
  if (!input) return "";
  if (!input.value) {
    const d = new Date();
    input.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  return input.value;
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

async function fetchClinics() {
  try {
    if (window.api?.getClinics) {
      return await window.api.getClinics();
    }
  } catch (e) {
    console.warn("getClinics failed", e);
  }

  if (Array.isArray(window.clinics)) {
    return window.clinics.map((c) => ({ id: c.id, name: c.name }));
  }

  return [];
}

async function fetchClinicPosts(clinicId, month, type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
  });
  const url = `${API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

async function loadCalendar() {
  const clinicSelect = document.getElementById("calendarClinicSelect");
  const month = getMonthValue();
  if (!clinicSelect || !month) return;

  const clinicId = clinicSelect.value;
  const clinics = clinicSelect.dataset.clinics
    ? JSON.parse(clinicSelect.dataset.clinics)
    : [];

  const targetClinics = clinicId === "all"
    ? clinics
    : clinics.filter((c) => String(c.id) === clinicId);

  const items = [];

  await Promise.all(targetClinics.map(async (clinic) => {
    const [opinions, reviews] = await Promise.all([
      fetchClinicPosts(clinic.id, month, "opinion"),
      fetchClinicPosts(clinic.id, month, "review"),
    ]);

    [...opinions, ...reviews].forEach((post) => {
      const subtype = post.review_subtype === "photo" ? "사진" : post.review_subtype === "text" ? "텍스트" : "";
      const typeLabel = post.type === "review" ? "후기" : "여론";
      const titlePrefix = subtype ? `[${typeLabel}/${subtype}]` : `[${typeLabel}]`;
      items.push({
        date: getPostDate(post),
        title: `${titlePrefix} ${post.title}`,
        url: post.url,
        platform: post.platform_label || post.platform,
        status: post.status,
        account: post.assignee_name || "",
        views: post.views ?? 0,
        comments: post.comments ?? 0,
        message_count: post.message_count ?? 0,
        post_id: post.id,
        photos: (post.photos || []).map((p) => p.url),
        clinic: clinic.name,
        clinicId: clinic.id,
      });
    });
  }));

  renderScheduleCalendar({
    calendarId: "calendarBoard",
    listId: "calendarList",
    items,
    yearMonth: month,
    emptyMessage: "선택된 기간에 작업이 없습니다.",
  });
}

async function initCalendarDashboard() {
  const clinicSelect = document.getElementById("calendarClinicSelect");
  const refreshBtn = document.getElementById("calendarRefreshBtn");
  if (!clinicSelect || !refreshBtn) return;

  const clinics = await fetchClinics();
  clinicSelect.dataset.clinics = JSON.stringify(clinics);
  clinicSelect.innerHTML = `
    <option value="all">전체 병원</option>
    ${clinics.map((c) => `<option value="${c.id}">${c.name}</option>`).join("")}
  `;

  refreshBtn.onclick = loadCalendar;
  clinicSelect.onchange = loadCalendar;
  const monthInput = document.getElementById("calendarMonth");
  if (monthInput) {
    monthInput.addEventListener("change", loadCalendar);
  }

  loadCalendar();
}

document.addEventListener("DOMContentLoaded", initCalendarDashboard);
