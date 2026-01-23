console.log("clinic_page.js loaded");

const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";
const LAST_CLINIC_KEY = "lastClinicId";

// ================================
// 상태
// ================================
let currentClinicId = null;
let currentMonth = getThisMonth();   // YYYY-MM
let currentType = "opinion";         // opinion | review
let currentPlatform = "all";         // all | naver | ...
let currentQuery = "";

// ================================
// 플랫폼 정의
// ================================
const PLATFORM_PILLS = [
  { key: "all", label: "전체" },
  { key: "naver", label: "네이버" },
  { key: "gn_jp", label: "JP강남언니" },
  { key: "gangnam", label: "강남언니" },
  { key: "babytok", label: "바비톡" },
  { key: "todaktok", label: "토닥톡" },
  { key: "yeoshin", label: "여신티켓" },
  { key: "seongyesa", label: "성예사" },
  { key: "dadamo", label: "대다모" },
];

// ================================
// 인증 헤더
// ================================
async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

// ================================
// 유틸
// ================================
function getClinicIdFromQuery() {
  return new URLSearchParams(window.location.search).get("clinic_id");
}

function normalizeClinicId(raw) {
  const value = String(raw || "").trim();
  if (!value || value === "null" || value === "undefined") return null;
  return value;
}

function rememberClinicId(clinicId) {
  if (!clinicId) return;
  localStorage.setItem(LAST_CLINIC_KEY, String(clinicId));
}

function getRememberedClinicId() {
  return normalizeClinicId(localStorage.getItem(LAST_CLINIC_KEY));
}

function getThisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function fmtDateTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", { hour12: false });
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ================================
// 초기 로드
// ================================
async function initClinicPage() {
  currentClinicId = normalizeClinicId(getClinicIdFromQuery()) || getRememberedClinicId();
  if (!currentClinicId) {
    window.showAlert?.("clinic_id 없음");
    return;
  }
  rememberClinicId(currentClinicId);

  await loadClinicInfo();

  initAiIntakeForm();
  bindPostsDashboardLink();
}

// ================================
// 병원 정보
// ================================
async function loadClinicInfo() {
  if (!currentClinicId) return;
  const data = await window.api.getClinicDetail(currentClinicId);
  const c = data?.clinic || {};

  const titleEl = document.getElementById("clinicTitle");
  const metaEl = document.getElementById("clinicMeta");

  if (titleEl) {
    titleEl.innerText = c.name || "병원";
  }

  if (metaEl) {
    metaEl.innerText = `${c.location || ""} · ${c.hours || ""}`.trim();
  }
}

// ================================
// 플랫폼 / 타입 / 검색
// ================================
function renderPlatformPills() {
  const root = document.getElementById("platformPills");
  if (!root) return;

  root.innerHTML = PLATFORM_PILLS.map(p => `
    <button class="pill ${p.key === "all" ? "active" : ""}"
            data-platform="${p.key}"
            onclick="setPlatform('${p.key}')">
      ${p.label}
    </button>
  `).join("");
}

function setPlatform(key) {
  currentPlatform = key;

  document.querySelectorAll("#platformPills .pill").forEach(el => {
    el.classList.toggle("active", el.dataset.platform === key);
  });

  loadPosts();
}

function setPostType(type) {
  currentType = type;

  document.querySelectorAll(".seg-tab").forEach(el => {
    el.classList.toggle("active", el.dataset.type === type);
  });

  loadPosts();
}

function bindSearch() {
  const el = document.getElementById("postSearch");
  if (!el) return;

  el.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      currentQuery = el.value.trim();
      loadPosts();
    }
  });
}

function initMonthSelect() {
  const sel = document.getElementById("monthFilter");
  if (!sel) return;
  sel.value = currentMonth;
  sel.onchange = () => {
    currentMonth = sel.value;
    loadPosts();
  };
}

function initAiIntakeForm() {
  const urlInput = document.getElementById("aiIntakeUrl");
  const titleInput = document.getElementById("aiIntakeTitle");
  const accountInput = document.getElementById("aiIntakeAccount");
  const accountPasswordInput = document.getElementById("aiIntakeAccountPassword");
  const memoInput = document.getElementById("aiIntakeMemo");
  const doctorInput = document.getElementById("aiIntakeDoctor");
  const platformSelect = document.getElementById("aiIntakePlatform");
  const platformHint = document.getElementById("aiIntakePlatformHint");
  const typePills = document.getElementById("aiIntakeTypePills");
  const submitBtn = document.getElementById("aiIntakeSubmit");
  const reviewBtn = document.getElementById("aiIntakeReviewBtn");
  const statusEl = document.getElementById("aiIntakeStatus");
  const photoInput = document.getElementById("aiIntakePhotos");
  const photoHint = document.getElementById("aiIntakePhotoHint");
  const reviewMenu = document.querySelector(".ai-review-menu");

  const confirmModal = document.getElementById("aiConfirmModal");
  const confirmUrl = document.getElementById("aiConfirmUrl");
  const confirmTitle = document.getElementById("aiConfirmTitle");
  const confirmAccount = document.getElementById("aiConfirmAccount");
  const confirmAccountPassword = document.getElementById("aiConfirmAccountPassword");
  const confirmMemo = document.getElementById("aiConfirmMemo");
  const confirmDoctor = document.getElementById("aiConfirmDoctor");
  const confirmPlatform = document.getElementById("aiConfirmPlatform");
  const confirmTypePills = document.getElementById("aiConfirmTypePills");
  const confirmSubtype = document.getElementById("aiConfirmSubtype");
  const confirmPhotos = document.getElementById("aiConfirmPhotos");
  const confirmPhotoHint = document.getElementById("aiConfirmPhotoHint");
  const confirmSummary = document.getElementById("aiConfirmSummary");
  const confirmEdit = document.getElementById("aiConfirmEdit");
  const confirmEditBtn = document.getElementById("aiConfirmEditBtn");
  const confirmTypeText = document.getElementById("aiConfirmTypeText");
  const confirmSubtypeText = document.getElementById("aiConfirmSubtypeText");
  const confirmPlatformText = document.getElementById("aiConfirmPlatformText");
  const confirmUrlText = document.getElementById("aiConfirmUrlText");
  const confirmTitleText = document.getElementById("aiConfirmTitleText");
  const confirmAccountText = document.getElementById("aiConfirmAccountText");
  const confirmAccountPasswordText = document.getElementById("aiConfirmAccountPasswordText");
  const confirmMemoText = document.getElementById("aiConfirmMemoText");
  const confirmDoctorText = document.getElementById("aiConfirmDoctorText");
  const confirmDateText = document.getElementById("aiConfirmDateText");
  const confirmPhotoText = document.getElementById("aiConfirmPhotoText");
  const confirmPhotoPreview = document.getElementById("aiConfirmPhotoPreview");
  const photoPreviewModal = document.getElementById("photoPreviewModal");
  const photoPreviewImage = document.getElementById("photoPreviewImage");
  const confirmSave = document.getElementById("aiConfirmSave");
  const confirmCancel = document.getElementById("aiConfirmCancel");

  if (!urlInput || !platformSelect || !submitBtn) return;

  let currentIntakeType = "opinion";
  let platformManual = false;
  let currentReviewSubtype = "text";
  let intakeFiles = [];
  let confirmFiles = [];

  const fileKey = (file) => `${file.name}|${file.size}|${file.lastModified}`;

  const addFiles = (targetList, files) => {
    const existing = new Set(targetList.map(fileKey));
    Array.from(files || []).forEach((file) => {
      if (!existing.has(fileKey(file))) {
        targetList.push(file);
        existing.add(fileKey(file));
      }
    });
  };

  const updateFileHint = (hintEl, list) => {
    if (!hintEl) return;
    hintEl.textContent = list.length ? `${list.length}개 파일 선택됨` : "선택된 파일 없음";
  };

  const detectPlatformFromUrl = (url) => {
    const raw = String(url || "").toLowerCase();
    if (!raw) return null;
    const candidates = [
      { key: "naver", label: "네이버", match: ["naver.com", "blog.naver.com", "m.blog.naver.com", "cafe.naver.com"] },
      { key: "gangnam", label: "강남언니", match: ["abr.ge", "gangnamunni.com", "gangnamunni", "gangnam"] },
      { key: "gn_jp", label: "JP강남언니", match: ["gnun.link", "gangnamunni.jp", "gn.jp", "gangnam-jp"] },
      { key: "babytok", label: "바비톡", match: ["web.babitalk.com", "babitalk.com", "babytok.com", "babytok"] },
      { key: "todaktok", label: "토닥톡", match: ["todaktok.com", "todaktok"] },
      { key: "yeoshin", label: "여신티켓", match: ["yeoshin.co.kr", "yeoshin.com", "yeoshin", "yeoshin-ticket"] },
      { key: "seongyesa", label: "성예사", match: ["sungyesa.com", "seongyesa.com", "seongyesa"] },
      { key: "dadamo", label: "대다모", match: ["daedamo.com", "dadamo.com", "dadamo"] },
    ];
    const hit = candidates.find((c) => c.match.some((m) => raw.includes(m)));
    return hit ? { key: hit.key, label: hit.label } : null;
  };

  const syncPlatformAuto = () => {
    const info = detectPlatformFromUrl(urlInput.value);
    if (!platformManual || !platformSelect.value) {
      platformSelect.value = info ? info.key : "";
    }
    if (platformHint) {
      platformHint.textContent = info
        ? `자동 선택 (${info.label})`
        : "자동 선택 실패 (직접 선택)";
    }
  };

  if (!platformSelect.options.length) {
    platformSelect.innerHTML = `
      <option value="">플랫폼 선택</option>
      ${PLATFORM_PILLS.filter(p => p.key !== "all")
        .map(p => `<option value="${p.key}">${p.label}</option>`)
        .join("")}
    `;
  }

  if (typePills) {
    typePills.querySelectorAll(".seg-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentIntakeType = btn.dataset.type || "opinion";
        typePills.querySelectorAll(".seg-tab").forEach((b) => b.classList.toggle("active", b === btn));
      });
    });
  }

  if (platformSelect) {
    platformSelect.addEventListener("change", () => {
      platformManual = true;
    });
  }

  if (confirmSubtype && !confirmSubtype.options.length) {
    confirmSubtype.innerHTML = `
      <option value="text">텍스트 후기</option>
      <option value="photo">사진 후기</option>
      <option value="consultation">상담 후기</option>
    `;
  }

  urlInput.addEventListener("input", syncPlatformAuto);

  const closeConfirmModal = () => {
    if (confirmModal) confirmModal.classList.add("hidden");
  };

  const toggleConfirmEdit = (editing) => {
    if (confirmSummary) confirmSummary.classList.toggle("hidden", editing);
    if (confirmEdit) confirmEdit.classList.toggle("hidden", !editing);
    if (confirmEditBtn) confirmEditBtn.classList.toggle("hidden", editing);
  };

  const syncSubtypeVisibility = () => {
    const isReview = (confirmTypePills?.querySelector(".seg-tab.active")?.dataset?.type || currentIntakeType) === "review";
    if (confirmSubtype) {
      confirmSubtype.closest(".ai-field")?.classList.toggle("hidden", !isReview);
    }
  };

  const openConfirmModal = () => {
    if (!confirmModal) return;
    confirmFiles = [];
    if (confirmPlatform && !confirmPlatform.options.length) {
      confirmPlatform.innerHTML = platformSelect.innerHTML;
    }
    if (confirmUrl) confirmUrl.value = urlInput.value.trim();
    if (confirmTitle) confirmTitle.value = (titleInput?.value || "").trim();
    if (confirmAccount) confirmAccount.value = (accountInput?.value || "").trim();
    if (confirmAccountPassword) confirmAccountPassword.value = (accountPasswordInput?.value || "").trim();
    if (confirmMemo) confirmMemo.value = (memoInput?.value || "").trim();
    if (confirmDoctor) confirmDoctor.value = (doctorInput?.value || "").trim();
    if (confirmPlatform) confirmPlatform.value = platformSelect.value;
    if (confirmTypePills) {
      confirmTypePills.querySelectorAll(".seg-tab").forEach((b) => {
        b.classList.toggle("active", b.dataset.type === currentIntakeType);
      });
    }
    if (confirmSubtype) {
      if (currentIntakeType === "review") {
        const photoCount = photoInput?.files?.length || 0;
        currentReviewSubtype = photoCount ? "photo" : "text";
      } else {
        currentReviewSubtype = "text";
      }
      confirmSubtype.value = currentReviewSubtype;
    }
    updateFileHint(confirmPhotoHint, intakeFiles);
    if (confirmTypeText) {
      confirmTypeText.textContent = currentIntakeType === "review" ? "후기" : "여론";
    }
    if (confirmSubtypeText) {
      if (currentIntakeType === "review") {
        const label = confirmSubtype?.selectedOptions?.[0]?.textContent || "텍스트 후기";
        confirmSubtypeText.textContent = label;
      } else {
        confirmSubtypeText.textContent = "텍스트 여론";
      }
    }
    if (confirmPlatformText) {
      const label = platformSelect?.selectedOptions?.[0]?.textContent || "-";
      confirmPlatformText.textContent = label;
    }
    if (confirmUrlText) confirmUrlText.textContent = confirmUrl?.value || "-";
    if (confirmTitleText) confirmTitleText.textContent = confirmTitle?.value || "-";
    if (confirmAccountText) confirmAccountText.textContent = confirmAccount?.value || "-";
    if (confirmAccountPasswordText) confirmAccountPasswordText.textContent = confirmAccountPassword?.value || "-";
    if (confirmMemoText) confirmMemoText.textContent = confirmMemo?.value || "-";
    if (confirmDoctorText) confirmDoctorText.textContent = confirmDoctor?.value || "-";
    if (confirmDateText) {
      const now = new Date();
      confirmDateText.textContent = now.toLocaleDateString("ko-KR");
    }
    if (confirmPhotoText) {
      confirmPhotoText.textContent = intakeFiles.length ? `${intakeFiles.length}개` : "없음";
    }
    if (confirmPhotoPreview) {
      const files = intakeFiles;
      if (!files.length) {
        confirmPhotoPreview.innerHTML = "<span class='muted'>없음</span>";
      } else {
        confirmPhotoPreview.innerHTML = files
          .slice(0, 4)
          .map((file) => {
            const url = URL.createObjectURL(file);
            return `<img src="${url}" alt="preview" data-preview="${url}" />`;
          })
          .join("");
        confirmPhotoPreview.querySelectorAll("img").forEach((img) => {
          img.addEventListener("click", (e) => {
            e.stopPropagation();
            if (!photoPreviewModal || !photoPreviewImage) return;
            photoPreviewImage.src = img.dataset.preview || img.src;
            photoPreviewModal.classList.remove("hidden");
          });
        });
      }
    }
    syncSubtypeVisibility();
    toggleConfirmEdit(false);
    confirmModal.classList.remove("hidden");
  };

  const bindConfirmTypePills = () => {
    if (!confirmTypePills) return;
    confirmTypePills.querySelectorAll(".seg-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        confirmTypePills.querySelectorAll(".seg-tab").forEach((b) => b.classList.toggle("active", b === btn));
        syncSubtypeVisibility();
      });
    });
  };

  bindConfirmTypePills();

  if (confirmModal) {
    confirmModal.addEventListener("click", (e) => {
      const target = e.target;
      if (target?.dataset?.close) {
        closeConfirmModal();
      }
    });
  }

  if (photoPreviewModal) {
    photoPreviewModal.addEventListener("click", (e) => {
      const target = e.target;
      if (target?.dataset?.close) {
        photoPreviewModal.classList.add("hidden");
      }
    });
  }

  if (confirmEditBtn) {
    confirmEditBtn.addEventListener("click", () => toggleConfirmEdit(true));
  }

  if (confirmPhotos && confirmPhotoHint) {
    confirmPhotos.addEventListener("change", () => {
      addFiles(confirmFiles, confirmPhotos.files);
      updateFileHint(confirmPhotoHint, confirmFiles);
      confirmPhotos.value = "";
    });
  }

  submitBtn.onclick = () => {
    const url = urlInput.value.trim();
    if (!url) {
      if (statusEl) statusEl.textContent = "URL을 입력하세요.";
      return;
    }
    syncPlatformAuto();
    openConfirmModal();
  };

  if (confirmSave) {
    confirmSave.onclick = async () => {
      const url = confirmUrl?.value.trim() || "";
      const title = (confirmTitle?.value || "").trim();
      const account = (confirmAccount?.value || "").trim();
      const accountPassword = (confirmAccountPassword?.value || "").trim();
      const memo = (confirmMemo?.value || "").trim();
      const doctor = (confirmDoctor?.value || "").trim();
      const platform = confirmPlatform?.value || "";
      const type = confirmTypePills?.querySelector(".seg-tab.active")?.dataset?.type || currentIntakeType;
      const subtype = confirmSubtype?.value || "text";

      if (!url) {
        if (statusEl) statusEl.textContent = "URL을 입력하세요.";
        return;
      }
      if (!platform) {
        if (statusEl) statusEl.textContent = "플랫폼을 선택하세요.";
        return;
      }

      const form = new FormData();
      form.append("url", url);
      form.append("platform", platform);
      form.append("title", title);
      if (doctor) form.append("doctor_name", doctor);
      if (account) form.append("account", account);
      if (accountPassword) form.append("account_password", accountPassword);
      if (memo) form.append("memo", memo);
      form.append("type", type);
      if (type === "review") {
        form.append("review_subtype", subtype);
      }

      const sourceFiles = confirmFiles.length ? confirmFiles : intakeFiles;
      sourceFiles.forEach((file) => {
        form.append("photos", file);
      });

      if (statusEl) statusEl.textContent = "처리 중...";
      confirmSave.disabled = true;
      submitBtn.disabled = true;
      try {
        const headers = await buildAuthHeaders();
        const res = await fetch(
          `${API_BASE}/api/data/clinics/${currentClinicId}/posts/`,
          {
            method: "POST",
            credentials: "include",
            headers,
            body: form,
          }
        );

        if (!res.ok) {
          if (statusEl) statusEl.textContent = "저장 실패";
          return;
        }

        if (statusEl) statusEl.textContent = "저장 완료";
        urlInput.value = "";
        if (titleInput) titleInput.value = "";
        if (accountInput) accountInput.value = "";
        if (accountPasswordInput) accountPasswordInput.value = "";
        if (memoInput) memoInput.value = "";
        if (doctorInput) doctorInput.value = "";
        if (photoInput) photoInput.value = "";
        if (confirmPhotos) confirmPhotos.value = "";
        intakeFiles = [];
        confirmFiles = [];
        updateFileHint(photoHint, intakeFiles);
        updateFileHint(confirmPhotoHint, confirmFiles);
        if (confirmPhotoPreview) confirmPhotoPreview.innerHTML = "";
        platformSelect.value = "";
        platformManual = false;
        closeConfirmModal();
        await loadPosts();
      } catch (e) {
        console.error("ai intake error", e);
        if (statusEl) statusEl.textContent = "저장 실패";
      } finally {
        confirmSave.disabled = false;
        submitBtn.disabled = false;
      }
    };
  }

  if (reviewBtn) {
    reviewBtn.onclick = (e) => {
      e.stopPropagation();
      if (reviewMenu) reviewMenu.classList.toggle("open");
    };
  }

  if (reviewMenu) {
    reviewMenu.querySelectorAll(".menu-item").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const type = btn.dataset.type;
        reviewMenu.classList.remove("open");
        if (type === "gangnam") {
          window.location.href = `gangnam_review.html?clinic_id=${currentClinicId}`;
          return;
        }
        if (type === "babytok") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=babytok`;
          return;
        }
        if (type === "todaktok") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=todaktok`;
          return;
        }
        if (type === "yeoshin") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=yeoshin`;
          return;
        }
        window.location.href = `review.html?clinic_id=${currentClinicId}`;
      });
    });

    document.addEventListener("click", () => {
      reviewMenu.classList.remove("open");
    });
  }

  if (photoInput && photoHint) {
    photoInput.addEventListener("change", () => {
      addFiles(intakeFiles, photoInput.files);
      updateFileHint(photoHint, intakeFiles);
      photoInput.value = "";
    });
  }
}

function bindPostsDashboardLink() {
  const btn = document.getElementById("goPostsDashboard");
  if (!btn) return;
  btn.addEventListener("click", () => {
    window.nav.go(`posts_dashboard?clinic_id=${currentClinicId}`);
  });
}

// ================================
// 게시글 로드
// ================================
async function loadPosts() {
  if (!currentClinicId) return;
  const root = document.getElementById("postList");
  if (!root) return;

  root.innerHTML = `<div class="muted">불러오는 중...</div>`;

  const params = new URLSearchParams({
    type: currentType,
    platform: currentPlatform,
    month: currentMonth,
  });

  if (currentQuery) {
    params.set("q", currentQuery);
  }

  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;

  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
  const data = await res.json();

  if (!data.results || data.results.length === 0) {
    root.innerHTML = `<div class="muted">표시할 게시글이 없습니다.</div>`;
    return;
  }

  root.innerHTML = data.results.map(p => `
    <div class="post-row">
      <div class="post-platform">${p.platform}</div>
      <div class="post-title">
        <a href="${p.url}" target="_blank">${escapeHtml(p.title)}</a>
      </div>
      <div class="post-num">${p.views}</div>
      <div class="post-num">${p.comments}</div>
      <div>
        <input class="post-input message-input" type="number" min="0" value="${p.message_count ?? 0}" data-post-id="${p.id}" />
      </div>
      <div class="post-status">${p.status}</div>
      <div class="post-updated">${fmtDateTime(p.updated_at)}</div>
    </div>
  `).join("");

  bindMessageInputs();
}

function bindMessageInputs() {
  document.querySelectorAll(".message-input").forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        input.blur();
      }
    });
    input.addEventListener("blur", async () => {
      const postId = input.dataset.postId;
      const value = Number(input.value || 0);
      if (!postId) return;
      await updatePostMessageCount(postId, value);
    });
  });
}

async function updatePostMessageCount(postId, messageCount) {
  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`;
  try {
    const headers = await buildAuthHeaders();
    await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ message_count: messageCount }),
    });
  } catch (e) {
    console.error("message count update failed", e);
  }
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

async function fetchPostsByMonth(type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month: currentMonth,
  });

  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function reloadClinicPage() {
  loadPosts();
}

// ================================
// 시작
// ================================
document.addEventListener("DOMContentLoaded", initClinicPage);
