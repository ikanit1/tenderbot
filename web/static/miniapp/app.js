(function () {
  "use strict";

  const TG = window.Telegram && window.Telegram.WebApp;
  if (!TG) {
    document.getElementById("loader").innerHTML = "<p>Откройте приложение из Telegram.</p>";
    return;
  }

  TG.ready();
  TG.expand();

  const BASE = window.__MINIAPP_BASE__ || "";
  const API_BASE = BASE + "/miniapp";

  function getInitData() {
    return TG.initData || "";
  }

  function api(path, options = {}) {
    const url = (path.startsWith("http") ? path : API_BASE + path);
    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...options.headers,
    };
    return fetch(url, { ...options, headers }).then(async (r) => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || data.message || r.statusText || "Ошибка");
      return data;
    });
  }

  const state = {
    user: null,
    screen: "home",
    stack: [],
    tenders: [],
    applications: [],
    currentTenderId: null,
    currentApplicationId: null,
    skills: [],
  };

  const $ = (id) => document.getElementById(id);
  const main = $("main");
  const headerTitle = $("headerTitle");
  const btnBack = $("btnBack");
  const tabbar = $("tabbar");
  const app = $("app");
  const loader = $("loader");
  const errorScreen = $("error-screen");
  const errorText = $("errorText");

  function showLoader() {
    loader.classList.remove("hidden");
    app.classList.add("hidden");
    errorScreen.classList.add("hidden");
  }

  function showApp() {
    loader.classList.add("hidden");
    errorScreen.classList.add("hidden");
    app.classList.remove("hidden");
  }

  function showError(msg) {
    loader.classList.add("hidden");
    app.classList.add("hidden");
    errorScreen.classList.remove("hidden");
    errorText.textContent = msg;
  }

  function setHeader(title, showBack) {
    headerTitle.textContent = title;
    if (showBack) {
      btnBack.classList.remove("hidden");
    } else {
      btnBack.classList.add("hidden");
    }
  }

  function setTabbarActive(screen) {
    tabbar.querySelectorAll(".tabbar-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.screen === screen);
    });
  }

  function navigate(screen, push = true) {
    if (push && state.screen) state.stack.push(state.screen);
    state.screen = screen;
    setTabbarActive(screen);
    loadScreenData().then(() => render()).catch((err) => {
      if (TG && TG.showAlert) TG.showAlert(err.message || "Ошибка загрузки");
      render();
    });
  }

  function back() {
    if (state.stack.length) {
      state.screen = state.stack.pop();
      setTabbarActive(state.screen);
      loadScreenData().then(() => render()).catch(() => render());
    } else {
      navigate("home", false);
    }
  }

  function render() {
    const s = state.screen;
    setHeader(getScreenTitle(s), state.stack.length > 0);

    if (s === "home") main.innerHTML = renderHome();
    else if (s === "tenders") main.innerHTML = renderTendersList();
    else if (s === "tender" && state.currentTenderId) main.innerHTML = renderTenderDetail();
    else if (s === "applications") main.innerHTML = renderApplicationsList();
    else if (s === "application" && state.currentApplicationId) main.innerHTML = renderApplicationDetail();
    else if (s === "profile") main.innerHTML = renderProfile();
    else if (s === "profile_edit") main.innerHTML = renderProfileEdit();
    else main.innerHTML = "<p>Загрузка...</p>";

    bindEvents();
  }

  function getScreenTitle(s) {
    const titles = {
      home: "TenderBot",
      tenders: "Заказы",
      tender: "Заказ",
      applications: "Мои отклики",
      application: "Отклик",
      profile: "Профиль",
      profile_edit: "Редактирование",
    };
    return titles[s] || "TenderBot";
  }

  function renderHome() {
    const u = state.user;
    const statusText = u.status === "active" ? "Активен" : u.status === "pending_moderation" ? "На модерации" : "Заблокирован";
    return `
      <div class="screen">
        <div class="card welcome-card">
          <h2 class="card-title">Привет, ${escapeHtml(u.full_name)}!</h2>
          <p class="card-meta">${escapeHtml(u.city)} · ${statusText}</p>
          <p class="card-desc">Здесь вы можете просматривать заказы, откликаться и следить за своими откликами.</p>
        </div>
        <div class="quick-actions">
          <button type="button" class="btn btn-primary" data-go="tenders">📋 Смотреть заказы</button>
          <button type="button" class="btn btn-secondary" data-go="applications">📩 Мои отклики</button>
          <button type="button" class="btn btn-secondary" data-go="profile">👤 Профиль</button>
        </div>
      </div>
    `;
  }

  function renderTendersList() {
    const list = state.tenders.length
      ? state.tenders
          .map(
            (t) => `
        <div class="card tender-card" data-tender-id="${t.id}">
          <h3 class="card-title">${escapeHtml(t.title)} <span class="badge ${t.has_applied ? "badge-applied" : "badge-open"}">${t.has_applied ? "Отклик отправлен" : "Открыт"}</span></h3>
          <p class="card-meta">${escapeHtml(t.city)} · ${escapeHtml(t.category)} ${t.budget ? " · " + escapeHtml(t.budget) : ""}</p>
          <p class="card-desc">${escapeHtml((t.description || "").slice(0, 120))}${(t.description || "").length > 120 ? "…" : ""}</p>
        </div>
      `
          )
          .join("")
      : '<div class="empty-state"><div class="empty-icon">📋</div><p>Нет открытых заказов в вашем городе.</p></div>';
    return `<div class="screen"><h2 class="screen-title">Заказы</h2>${list}</div>`;
  }

  function renderTenderDetail() {
    const t = state.currentTender;
    if (!t) return '<div class="screen"><p>Загрузка...</p></div>';
    const deadlineStr = t.deadline ? new Date(t.deadline).toLocaleString("ru-RU") : "Не указан";
    const canApply = !t.has_applied && t.status === "open";
    return `
      <div class="screen">
        <div class="card">
          <h2 class="card-title">${escapeHtml(t.title)}</h2>
          <p class="card-meta">${escapeHtml(t.city)} · ${escapeHtml(t.category)}</p>
          <p class="card-meta">💰 ${escapeHtml(t.budget || "По договорённости")} · ⏰ ${deadlineStr}</p>
        </div>
        <div class="detail-section">
          <h3>Описание</h3>
          <p>${escapeHtml(t.description || "")}</p>
        </div>
        ${canApply ? '<button type="button" class="btn btn-primary" id="btnApply">📩 Откликнуться</button>' : t.has_applied ? '<p class="card-meta">✅ Вы уже откликнулись на этот заказ.</p>' : ""}
      </div>
    `;
  }

  function renderApplicationsList() {
    const list = state.applications.length
      ? state.applications
          .map(
            (a) => `
        <div class="card list-item" data-application-id="${a.id}">
          <h3 class="card-title">${escapeHtml(a.tender_title)} <span class="app-status ${a.status}">${statusLabel(a.status)}</span></h3>
          <p class="card-meta">${escapeHtml(a.tender_city)} · ${escapeHtml(a.tender_category)}</p>
        </div>
      `
          )
          .join("")
      : '<div class="empty-state"><div class="empty-icon">📩</div><p>У вас пока нет откликов.</p><p>Выберите заказ и нажмите «Откликнуться».</p></div>';
    return `<div class="screen"><h2 class="screen-title">Мои отклики</h2>${list}</div>`;
  }

  function statusLabel(s) {
    const l = { applied: "Ожидает", selected: "Выбран", rejected: "Отклонён" };
    return l[s] || s;
  }

  function renderApplicationDetail() {
    const a = state.currentApplication;
    if (!a) return '<div class="screen"><p>Загрузка...</p></div>';
    return `
      <div class="screen">
        <div class="card">
          <h2 class="card-title">${escapeHtml(a.tender_title)}</h2>
          <p class="card-meta">Статус: ${statusLabel(a.status)}</p>
          <p class="card-meta">${escapeHtml(a.tender_city)} · ${escapeHtml(a.tender_category)} · ${escapeHtml(a.tender_budget || "По договорённости")}</p>
        </div>
        <div class="detail-section">
          <h3>Описание заказа</h3>
          <p>${escapeHtml(a.tender_description || "")}</p>
        </div>
        <p class="card-meta">Дата отклика: ${a.created_at ? new Date(a.created_at).toLocaleString("ru-RU") : "—"}</p>
      </div>
    `;
  }

  function renderProfile() {
    const u = state.user;
    if (!u) return "";
    const skillsStr = (u.skills && u.skills.length) ? u.skills.join(", ") : "—";
    return `
      <div class="screen">
        <h2 class="screen-title">Профиль</h2>
        <div class="card">
          <div class="profile-row">
            <span class="profile-label">ФИО</span>
            <span class="profile-value">${escapeHtml(u.full_name)}</span>
          </div>
          <div class="profile-row">
            <span class="profile-label">Город</span>
            <span class="profile-value">${escapeHtml(u.city)}</span>
          </div>
          <div class="profile-row">
            <span class="profile-label">Телефон</span>
            <span class="profile-value">${escapeHtml(u.phone)}</span>
          </div>
          <div class="profile-row">
            <span class="profile-label">Навыки</span>
            <span class="profile-value">${escapeHtml(skillsStr)}</span>
          </div>
          <div class="profile-row">
            <span class="profile-label">Статус</span>
            <span class="profile-value">${u.status === "active" ? "Активен" : u.status === "pending_moderation" ? "На модерации" : "Заблокирован"}</span>
          </div>
        </div>
        <button type="button" class="btn btn-secondary" data-go="profile_edit">✏️ Редактировать</button>
      </div>
    `;
  }

  function renderProfileEdit() {
    const u = state.user;
    if (!u) return "";
    const skillsOptions = (state.skills || []).map((sk) => `<option value="${escapeHtml(sk)}" ${(u.skills || []).includes(sk) ? "selected" : ""}>${escapeHtml(sk)}</option>`).join("");
    return `
      <div class="screen">
        <h2 class="screen-title">Редактирование профиля</h2>
        <form id="profileForm">
          <div class="form-group">
            <label>ФИО</label>
            <input type="text" name="full_name" value="${escapeHtml(u.full_name)}" required>
          </div>
          <div class="form-group">
            <label>Город</label>
            <input type="text" name="city" value="${escapeHtml(u.city)}" required>
          </div>
          <div class="form-group">
            <label>Телефон</label>
            <input type="text" name="phone" value="${escapeHtml(u.phone)}" required>
          </div>
          <div class="form-group">
            <label>Навыки (через запятую или выберите)</label>
            <input type="text" name="skills_text" placeholder="Например: СКУД, Видеонаблюдение" value="${escapeHtml((u.skills || []).join(", "))}">
          </div>
          <button type="submit" class="btn btn-primary">Сохранить</button>
        </form>
      </div>
    `;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function bindEvents() {
    main.querySelectorAll("[data-go]").forEach((el) => {
      el.addEventListener("click", () => navigate(el.dataset.go, true));
    });
    main.querySelectorAll("[data-tender-id]").forEach((el) => {
      el.addEventListener("click", () => {
        state.currentTenderId = parseInt(el.dataset.tenderId, 10);
        state.stack.push(state.screen);
        state.screen = "tender";
        loadTenderDetail().then(() => {
          setHeader("Заказ", true);
          setTabbarActive("tender");
          render();
        });
      });
    });
    main.querySelectorAll("[data-application-id]").forEach((el) => {
      el.addEventListener("click", () => {
        state.currentApplicationId = parseInt(el.dataset.applicationId, 10);
        state.stack.push(state.screen);
        state.screen = "application";
        loadApplicationDetail().then(() => {
          setHeader("Отклик", true);
          setTabbarActive("application");
          render();
        });
      });
    });
    const btnApply = main.querySelector("#btnApply");
    if (btnApply) {
      btnApply.addEventListener("click", () => applyToTender(state.currentTenderId));
    }
    const form = main.querySelector("#profileForm");
    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const skillsText = (fd.get("skills_text") || "").toString().trim();
        const skills = skillsText ? skillsText.split(/,\s*/).map((s) => s.trim()).filter(Boolean) : [];
        api("/api/profile", {
          method: "PATCH",
          body: JSON.stringify({
            full_name: fd.get("full_name"),
            city: fd.get("city"),
            phone: fd.get("phone"),
            skills: skills.length ? skills : state.user.skills,
          }),
        }).then(() => {
          state.stack.pop();
          return loadMe();
        }).then(() => {
          state.screen = "profile";
          setTabbarActive("profile");
          render();
        }).catch((err) => {
          TG.showAlert(err.message || "Ошибка сохранения");
        });
      });
    }
  }

  btnBack.addEventListener("click", back);
  tabbar.querySelectorAll(".tabbar-item").forEach((el) => {
    el.addEventListener("click", () => {
      const screen = el.dataset.screen;
      if (screen === state.screen) return;
      state.stack = [];
      navigate(screen, false);
    });
  });

  function loadMe() {
    return api("/api/me").then((data) => {
      state.user = data;
      return data;
    });
  }

  function loadTenders() {
    return api("/api/tenders").then((data) => {
      state.tenders = data.tenders || [];
      return data;
    });
  }

  function loadTenderDetail() {
    return api("/api/tenders/" + state.currentTenderId).then((data) => {
      state.currentTender = data;
      return data;
    });
  }

  function loadApplications() {
    return api("/api/applications").then((data) => {
      state.applications = data.applications || [];
      return data;
    });
  }

  function loadApplicationDetail() {
    return api("/api/applications/" + state.currentApplicationId).then((data) => {
      state.currentApplication = data;
      return data;
    });
  }

  function loadSkills() {
    return api("/api/skills").then((data) => {
      state.skills = data.skills || [];
      return data;
    });
  }

  function applyToTender(tenderId) {
    const btn = main.querySelector("#btnApply");
    if (btn) btn.disabled = true;
    api("/api/tenders/" + tenderId + "/apply", { method: "POST" })
      .then(() => {
        TG.showAlert("Отклик отправлен! Ожидайте решения заказчика.");
        state.currentTender.has_applied = true;
        state.currentTender.application_status = "applied";
        render();
      })
      .catch((err) => {
        TG.showAlert(err.message || "Не удалось отправить отклик");
        if (btn) btn.disabled = false;
      });
  }

  function loadScreenData() {
    const s = state.screen;
    if (s === "tenders") return loadTenders();
    if (s === "applications") return loadApplications();
    if (s === "profile_edit") return loadSkills();
    return Promise.resolve();
  }

  showLoader();
  loadMe()
    .then(() => {
      showApp();
      state.stack = [];
      setTabbarActive(state.screen);
      return loadScreenData();
    })
    .then(() => render())
    .catch((err) => {
      showError(err.message || "Не удалось загрузить данные. Пройдите регистрацию в боте.");
    });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && state.user && app.classList.contains("hidden") === false) {
      loadMe().then(() => {
        loadScreenData().then(() => render());
      });
    }
  });
})();
