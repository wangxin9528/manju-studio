/* global window, document, fetch, sessionStorage, history */
(() => {
  "use strict";

  // ---------------------------------------------------------------------
  // constants
  // ---------------------------------------------------------------------
  const STYLES = [
    { id: "neo_noir", name: "霓虹黑", tag: "NEON NOIR", note: "冷雨 / 悬疑 / 赛博", colors: ["#63F2DE", "#FF4D3D", "#0E1B2B"] },
    { id: "dusk_anime", name: "晚霞日漫", tag: "DUSK ANIME", note: "青春 / 逆光 / 情绪", colors: ["#FFD36E", "#B9587A", "#43305B"] },
    { id: "ink_wuxia", name: "水墨朱砂", tag: "INK WUXIA", note: "古风 / 刀光 / 宿命", colors: ["#C7352B", "#D9B56B", "#1C1A17"] },
    { id: "warm_slice", name: "暖调都市", tag: "WARM SLICE", note: "情感 / 生活 / 遗憾", colors: ["#E4553F", "#F4C26B", "#2C1C2B"] },
    { id: "cyber_pop", name: "赛博波普", tag: "CYBER POP", note: "高饱和 / 怪诞 / 未来", colors: ["#FF2E88", "#43F9FF", "#1B0B3A"] },
  ];
  const GENRES = ["都市悬疑", "热血玄幻", "古风仙侠", "都市情感", "青春校园"];
  const EMOTIONS = ["冷淡", "冷静", "低沉", "轻快", "失真", "颤抖", "动摇", "克制", "决绝", "逼近", "低语", "neutral"];
  const VOICES = [
    ["zh-CN-XiaoxiaoNeural", "晓晓 · 清冷少女"],
    ["zh-CN-XiaoyiNeural", "晓伊 · 明亮少女"],
    ["zh-CN-YunjianNeural", "云健 · 低沉男声"],
    ["zh-CN-YunxiNeural", "云希 · 轻快少年"],
    ["zh-CN-YunyangNeural", "云扬 · 旁白男声"],
    ["zh-CN-YunxiaNeural", "云夏 · 少年"],
  ];

  const state = {
    projects: [],
    config: null,
    health: null,
    project: null,
    episodeIndex: 1,
    tab: "story",
    job: null,
    pollTimer: null,
    loading: true,
  };

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDuration = (seconds) => {
    const s = Number(seconds || 0);
    if (!s) return "—";
    const m = Math.floor(s / 60);
    const r = Math.round(s % 60);
    return m ? `${m}′${String(r).padStart(2, "0")}″` : `${r}″`;
  };
  const fmtMinutes = (seconds) => {
    const s = Number(seconds || 0);
    return s ? `${Math.max(1, Math.round(s / 60))}` : "0";
  };
  const fmtDate = (iso) => {
    if (!iso) return "—";
    try {
      return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
    } catch { return "—"; }
  };
  const styleOf = (id) => STYLES.find((s) => s.id === id) || STYLES[0];

  // ---------------------------------------------------------------------
  // api / ui helpers
  // ---------------------------------------------------------------------
  async function api(path, options = {}) {
    const opts = { headers: { "Content-Type": "application/json" }, ...options };
    if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch { /* ignore */ }
    if (!res.ok) {
      const detail = data && (data.detail || data.error);
      throw new Error(typeof detail === "string" ? detail : `请求失败（${res.status}）`);
    }
    return data;
  }

  function toast(message, type = "ok") {
    const root = $("#toastRoot");
    const el = document.createElement("div");
    el.className = `toast ${type === "error" ? "err" : ""}`;
    el.textContent = message;
    root.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 320); }, 3400);
  }

  function icon(name, cls = "") {
    const paths = {
      arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
      play: '<path d="M8 5v14l11-7z"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      close: '<path d="M6 6l12 12M18 6L6 18"/>',
      back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
      download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
      spark: '<path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z"/>',
      settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
      refresh: '<path d="M20 11a8 8 0 1 0-2.3 6.3M20 4v7h-7"/>',
      edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>',
    };
    return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ""}</svg>`;
  }

  function updateSidebar(active) {
    $$(".navItem").forEach((el) => el.classList.toggle("active", el.dataset.nav === active));
    const health = state.health;
    if (health) {
      $("#sideStatus").textContent = health.ffmpeg ? "本地引擎已就绪" : "缺少 FFmpeg";
    }
  }

  // ---------------------------------------------------------------------
  // routing
  // ---------------------------------------------------------------------
  function navigate(path, replace = false) {
    if (replace) history.replaceState({}, "", path);
    else history.pushState({}, "", path);
    route();
  }

  document.addEventListener("click", (e) => {
    const link = e.target.closest("a[data-link]");
    if (link) {
      e.preventDefault();
      const href = link.getAttribute("href");
      if (href.startsWith("/#")) {
        navigate("/");
        setTimeout(() => $(href.slice(1))?.scrollIntoView({ behavior: "smooth" }), 120);
      } else if (href === "/settings") {
        openSettings();
      } else {
        navigate(href);
      }
      return;
    }
    const nav = e.target.closest("[data-nav]");
    if (nav && !nav.closest("a[data-link]")) {
      e.preventDefault();
      const name = nav.dataset.nav;
      if (name === "assets") openAssets();
      else if (name === "settings") openSettings();
      else navigate("/");
    }
  });

  window.addEventListener("popstate", () => route());

  async function route() {
    stopPolling();
    const path = window.location.pathname;
    if (path.startsWith("/studio/")) {
      const pid = decodeURIComponent(path.split("/")[2] || "");
      updateSidebar("dashboard");
      await loadStudio(pid);
      return;
    }
    updateSidebar(path === "/settings" ? "settings" : "dashboard");
    await loadDashboard();
    if (path === "/settings") openSettings(true);
  }

  async function boot() {
    try {
      const [health, settings, projects] = await Promise.all([
        api("/api/health"),
        api("/api/settings"),
        api("/api/projects"),
      ]);
      state.health = health;
      state.config = settings.config;
      state.projects = projects.projects;
      $("#sideStatus").textContent = health.ffmpeg ? "本地引擎已就绪" : "缺少 FFmpeg";
      await route();
    } catch (err) {
      $("#main").innerHTML = `<div class="loadingScreen"><div class="errorPanel">系统启动失败：${esc(err.message)}<br/><br/>请确认本地服务已启动，然后刷新页面。</div></div>`;
    }
  }

  // ---------------------------------------------------------------------
  // dashboard
  // ---------------------------------------------------------------------
  async function refreshProjects() {
    const data = await api("/api/projects");
    state.projects = data.projects;
  }

  async function loadDashboard() {
    if (!state.projects.length) await refreshProjects().catch(() => {});
    renderDashboard();
  }

  function renderDashboard() {
    const sample = state.projects.find((p) => p.sample) || state.projects[0];
    const totalEpisodes = state.projects.reduce((n, p) => n + (p.episode_count || 0), 0);
    const totalSeconds = state.projects.reduce((n, p) => n + (p.duration || 0), 0);
    const poster = sample?.cover
      ? `<img src="${esc(sample.cover)}" alt="${esc(sample.title)} 封面" />`
      : `<div class="shotFallback" style="position:absolute;inset:0"><span class="num">漫</span><span class="loc">LOCAL COVER</span></div>`;

    const cards = state.projects.map((p, i) => projectCard(p, i)).join("");
    $("#main").innerHTML = `
      <div class="topbar">
        <div class="crumb"><i></i> MANJU STUDIO <span>/</span> 本地片场 <span>/</span> ${new Date().getFullYear()}</div>
        <div class="topActions">
          <span class="chipStatus">${state.health?.ffmpeg ? "ENGINE READY" : "ENGINE CHECK"}</span>
          <button class="iconBtn" data-open-settings title="本地设置">${icon("settings")}</button>
        </div>
      </div>

      <section class="hero">
        <div class="heroCopy">
          <div class="eyebrow">Local-first AI motion comic</div>
          <h1>把一句话，<br />拍成一集<span class="red">漫剧</span>。</h1>
          <p class="heroLead">从剧本、分镜、漫画面板，到角色配音、氛围配乐与竖屏成片。<strong>画面与合成不出本机，不调用任何付费 API。</strong></p>
          <div class="heroActions">
            <button class="btn" data-open-new>${icon("plus")} 新建漫剧</button>
            ${sample ? `<button class="btn ghost" data-play-sample="${esc(sample.id)}">${icon("play")} 看本地样片</button>` : ""}
          </div>
          <div class="heroMeta">
            <span><i></i><b>0</b> API 费用</span>
            <span><i></i><b>9:16</b> 竖屏成片</span>
            <span><i></i><b>${state.health?.edge_tts ? "云端免费" : "本地"}</b> 中文配音</span>
            <span><i></i><b>${state.health?.ffmpeg ? "FFmpeg" : "未检测"}</b> 视频合成</span>
          </div>
        </div>
        <div class="posterStage">
          <div class="posterGhost"></div>
          <div class="posterStamp">SHOWREEL / 01</div>
          <div class="poster">
            ${poster}
            <button class="posterPlay" ${sample ? `data-play-sample="${esc(sample.id)}"` : "data-open-new"} aria-label="播放样片">${icon("play")}</button>
            <div class="posterMeta">
              <div class="mini">MANJU ORIGINAL</div>
              <h3>${esc(sample?.title || "你的第一部漫剧")}</h3>
              <p>${esc(sample ? `${sample.genre || ""} · 第 01 集` : "从一句创意开始")}</p>
            </div>
          </div>
          <div class="posterRing">LOCAL<br/>ONLY<br/>2026</div>
        </div>
      </section>

      <div class="metrics">
        <div class="metric"><b>${state.projects.length}<em>部</em></b><span>Projects / 项目</span></div>
        <div class="metric"><b>${totalEpisodes}<em>集</em></b><span>Episodes / 集数</span></div>
        <div class="metric"><b>${fmtMinutes(totalSeconds)}<em>min</em></b><span>Runtime / 时长</span></div>
        <div class="metric"><b>0<em>元</em></b><span>API Cost / 成本</span></div>
      </div>

      <section id="projects">
        <div class="sectionHead">
          <div>
            <h2>我的漫剧 <span>PROJECT LIBRARY</span></h2>
            <p>一个项目就是一部连续短剧。每个镜头都可以改，重新生成即可。</p>
          </div>
          <a href="/#projects" class="sectionLink" data-open-new>+ 新建项目</a>
        </div>
        <div class="projectGrid">
          ${cards || ""}
          <button class="newCard" data-open-new>
            <span class="newPlus">+</span>
            <span>一句话，新建一部漫剧</span>
          </button>
        </div>
      </section>

      <footer class="foot">
        <span>MANJU STUDIO v0.1 · LOCAL-FIRST · SHANGHAI / ${new Date().toLocaleDateString("zh-CN")}</span>
        <span><a href="https://github.com/HBAI-Ltd/Toonflow-app" target="_blank" rel="noreferrer">Inspired by Toonflow</a> · <a href="https://github.com/LingyiChen-AI/AIComicBuilder" target="_blank" rel="noreferrer">AIComicBuilder</a> · Made with FFmpeg + Edge TTS</span>
      </footer>`;

    bindDashboard(sample);
  }

  function projectCard(p, i) {
    const cover = p.cover
      ? `<img src="${esc(p.cover)}" alt="${esc(p.title)}" loading="lazy" />`
      : `<div class="shotFallback" style="position:absolute;inset:0"><span class="num">${String(i + 1).padStart(2, "0")}</span><span class="loc">${esc(p.style_name || styleOf(p.style).name)}</span></div>`;
    return `
      <article class="projectCard" data-project="${esc(p.id)}" style="animation-delay:${i * 45}ms">
        <div class="cardCover">
          ${cover}
          <span class="cardTag ${p.sample ? "sample" : ""}">${p.sample ? "样片 / SHOWREEL" : p.status === "ready" ? "READY" : "DRAFT"}</span>
          <span class="cardNum">${String(p.episode_count || 1).padStart(2, "0")}</span>
        </div>
        <div class="cardBody">
          <h3>${esc(p.title)}</h3>
          <p>${esc(p.logline || "一句话创意正在生长。")}</p>
          <div class="cardMeta">
            <span>${esc(p.genre || "漫剧")} · ${esc(p.style_name || "")}</span>
            <span><b>${p.episode_count || 1}</b> 集 · ${fmtDuration(p.duration)}</span>
          </div>
        </div>
      </article>`;
  }

  function bindDashboard(sample) {
    $$("[data-project]").forEach((el) => el.addEventListener("click", () => navigate(`/studio/${el.dataset.project}`)));
    $$("[data-open-new]").forEach((el) => el.addEventListener("click", openCreate));
    $$("[data-open-settings]").forEach((el) => el.addEventListener("click", () => openSettings()));
    $$("[data-play-sample]").forEach((el) => el.addEventListener("click", () => {
      const id = el.dataset.playSample;
      if (id) navigate(`/studio/${id}`);
    }));
  }

  // ---------------------------------------------------------------------
  // create modal
  // ---------------------------------------------------------------------
  function openCreate() {
    if (!state.health) return;
    let genre = "都市悬疑";
    let style = "neo_noir";
    openModal(`
      <div class="modalHead">
        <div>
          <div class="micro">NEW PROJECT / 本地生成</div>
          <h3>新建一部漫剧</h3>
          <p>写下最核心的那一句。剩下的交给本地导演引擎。</p>
        </div>
        <button class="modalClose" data-close>${icon("close")}</button>
      </div>
      <div class="modalBody">
        <div class="field">
          <label>故事创意 <b>必填</b></label>
          <textarea class="textarea" id="premiseInput" maxlength="240" placeholder="例：在记忆可以买卖的雾城，记忆修复师接到一单生意——修复一段被抹去的记忆，而记忆里的主角，正是她自己。"></textarea>
          <p class="hint">一句高概念即可。写清楚「谁 + 想要什么 + 但遇到什么」会更好看。</p>
        </div>
        <div class="fieldRow">
          <div class="field">
            <label>主角名 <span>可选</span></label>
            <input class="input" id="protagonistInput" placeholder="林雾" maxlength="12" />
          </div>
          <div class="field">
            <label>剧名 <span>可选</span></label>
            <input class="input" id="titleInput" placeholder="由引擎命名" maxlength="20" />
          </div>
        </div>
        <div class="field">
          <label>类型</label>
          <div class="chips" id="genreChips">
            ${GENRES.map((g) => `<button class="chip ${g === genre ? "active" : ""}" data-genre="${g}">${g}</button>`).join("")}
          </div>
        </div>
        <div class="field">
          <label>视觉风格</label>
          <div class="styleGrid" id="styleChips">
            ${STYLES.map((s) => `
              <button class="styleOption ${s.id === style ? "active" : ""}" data-style="${s.id}">
                <div class="styleSwatch" style="background:linear-gradient(135deg, ${s.colors[0]} 0%, ${s.colors[1]} 48%, ${s.colors[2]} 100%)"></div>
                <b>${s.name}</b><small>${s.tag}</small>
              </button>`).join("")}
          </div>
          <p class="hint" id="styleNote">${esc(styleOf(style).note)}</p>
        </div>
        <div class="switchRow">
          <div><b>调用本地大模型写剧本</b><small>${state.health?.llm_enabled ? "已启用 · 走设置里的 Ollama / OpenAI 兼容接口" : "未启用。仍可使用内置导演引擎，完全离线。"}</small></div>
          <label class="switch"><input type="checkbox" id="useLlm" ${state.health?.llm_enabled ? "" : "disabled"} /><i></i></label>
        </div>
        <div class="field" style="margin:16px 0 0">
          <label>预计产出</label>
          <p class="hint" style="margin:0">1 集 · 7–9 个镜头 · 约 45–70 秒 · 720×1280 · 中文配音与字幕</p>
        </div>
      </div>
      <div class="modalFoot">
        <button class="btn ghost" data-close>取消</button>
        <button class="btn" id="createBtn">${icon("spark")} 开始生成剧本</button>
      </div>`);

    $$("#genreChips [data-genre]").forEach((btn) => btn.addEventListener("click", () => {
      genre = btn.dataset.genre;
      $$("#genreChips [data-genre]").forEach((b) => b.classList.toggle("active", b === btn));
    }));
    $$("#styleChips [data-style]").forEach((btn) => btn.addEventListener("click", () => {
      style = btn.dataset.style;
      $$("#styleChips [data-style]").forEach((b) => b.classList.toggle("active", b === btn));
      $("#styleNote").textContent = styleOf(style).note;
    }));

    $("#createBtn").addEventListener("click", async () => {
      const premise = $("#premiseInput").value.trim();
      if (premise.length < 4) { toast("先写一句故事创意", "error"); $("#premiseInput").focus(); return; }
      const btn = $("#createBtn");
      btn.disabled = true;
      btn.textContent = "本地导演正在拆镜…";
      try {
        const data = await api("/api/projects", {
          method: "POST",
          body: {
            premise,
            genre,
            style,
            protagonist: $("#protagonistInput").value.trim(),
            title: $("#titleInput").value.trim(),
            use_llm: $("#useLlm")?.checked || false,
          },
        });
        closeModal();
        state.projects = [data.project, ...state.projects];
        toast(data.engine === "llm" ? "本地模型已完成第一集剧本" : "第一集剧本已生成");
        navigate(`/studio/${data.project.id}`);
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = `${icon("spark")} 开始生成剧本`;
        toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------------
  // studio
  // ---------------------------------------------------------------------
  async function loadStudio(pid) {
    stopPolling();
    $("#main").innerHTML = `<div class="loadingScreen"><span class="loadingMark">漫</span><span>正在进入片场…</span></div>`;
    try {
      const data = await api(`/api/projects/${pid}`);
      state.project = data.project;
      const eps = data.project.episodes || [];
      if (!eps.some((e) => e.index === state.episodeIndex)) state.episodeIndex = eps[0]?.index || 1;
      const savedJob = sessionStorage.getItem(`manju_job_${pid}`);
      if (savedJob) {
        try {
          const jobData = await api(`/api/jobs/${savedJob}`);
          const job = jobData.job;
          if (job.status === "running" || job.status === "queued") {
            state.job = job;
          } else {
            sessionStorage.removeItem(`manju_job_${pid}`);
          }
        } catch { sessionStorage.removeItem(`manju_job_${pid}`); }
      }
      renderStudio();
      if (state.job) startPolling();
    } catch (err) {
      $("#main").innerHTML = `<div class="loadingScreen"><div class="errorPanel">无法打开这个项目：${esc(err.message)}<br/><br/><a href="/" data-link style="color:var(--red)">返回工作台</a></div></div>`;
    }
  }

  function currentEpisode() {
    return state.project?.episodes?.find((e) => e.index === state.episodeIndex) || state.project?.episodes?.[0];
  }

  function renderStudio() {
    const p = state.project;
    if (!p) return;
    const ep = currentEpisode();
    if (!ep) return;
    state.episodeIndex = ep.index;
    const shots = ep.shots || [];
    const artCount = shots.filter((s) => s.image_url).length;
    const hasVideo = Boolean(ep.video);
    const style = styleOf(p.style);
    const job = state.job;
    const busy = job && (job.status === "running" || job.status === "queued");
    const outdated = hasVideo && ep.status === "edited";
    const statusText = busy ? "生成中" : outdated ? "已修改 · 待重生成" : hasVideo ? "成片就绪" : ep.status === "edited" ? "待重新生成" : "草稿";
    const statusClass = busy ? "working" : hasVideo && !outdated ? "ready" : "";
    const artEngine = state.health?.art_engine || state.config?.art?.engine || "builtin";
    const stepActive = (name) => (busy && job.stage === name ? "active" : "");
    const video = ep.video
      ? `<video controls playsinline preload="metadata" poster="${esc(ep.cover || "")}" src="${esc(ep.video)}"></video>`
      : ep.cover
        ? `<div class="stagePoster" style="background-image:url('${esc(ep.cover)}')"></div><div class="stagePlay">${icon("play")}</div>`
        : `<div class="stagePlaceholder"><div class="bigMark">漫</div><p>${artCount ? "画面已铺好，配音与合成后即可播放" : "还没有成片。点击右侧「生成本集」"}</p></div>`;

    const shotCards = shots.map((shot, i) => {
      const line = shot.dialogues && shot.dialogues.length
        ? `<span class="speaker">${esc(shot.dialogues[0].speaker)}</span>${esc(shot.dialogues[0].text)}`
        : esc(shot.narration || "（无台词）");
      const img = shot.image_url
        ? `<img src="${esc(shot.image_url)}" alt="第 ${shot.index} 镜" loading="lazy" />`
        : `<div class="shotFallback"><span class="num">${String(shot.index).padStart(2, "0")}</span><span class="loc">${esc(shot.location || "待生成画面")}</span></div>`;
      return `
        <article class="shotCard" data-shot="${esc(shot.id)}" style="animation-delay:${i * 35}ms">
          <div class="shotThumb">
            ${img}
            <span class="shotIndex">SHOT ${String(shot.index).padStart(2, "0")}</span>
            ${shot.ai_art ? '<span class="aiTag">AI</span>' : ""}
            <span class="shotCam">${esc(shot.shot_type || "")} · ${esc(shot.camera || "")}</span>
          </div>
          <div class="shotInfo">
            <div class="loc">${esc(shot.location || shot.scene || "")}</div>
            <p class="line">${line}</p>
            <span class="editHint">CLICK TO EDIT →</span>
          </div>
        </article>`;
    }).join("");

    const script = shots.map((shot) => {
      const lines = [];
      if (shot.narration) lines.push(`<div class="say"><b>${esc(shot.narration_speaker || "旁白")}（VO）</b>：${esc(shot.narration)}</div>`);
      (shot.dialogues || []).forEach((d) => lines.push(`<div class="say"><b>${esc(d.speaker)}</b>：${esc(d.text)}</div>`));
      return `<div class="scriptShot"><div class="head"><b>SHOT ${String(shot.index).padStart(2, "0")}</b><span>${esc(shot.location || "")}</span><span>${esc(shot.shot_type || "")} / ${esc(shot.camera || "")}</span></div><p>${esc(shot.caption || "—")}</p>${lines.join("") || '<div class="say">（无台词）</div>'}</div>`;
    }).join("");

    const charChips = (p.characters || []).map((c) => `
      <span class="charChip">${c.ref_url ? `<img class="charAvatar" src="${esc(c.ref_url)}" alt="${esc(c.name)}" />` : `<i style="background:${esc(c.accent || "#63F2DE")}"></i>`}${esc(c.name)} <small>${esc((c.voice || "").replace("zh-CN-", "").replace("Neural", ""))}</small></span>`).join("");

    $("#main").innerHTML = `
      <div class="topbar">
        <div class="crumb"><i></i> PROJECT <span>/</span> ${esc(p.id).toUpperCase()} <span>/</span> EP.${String(ep.index).padStart(2, "0")}</div>
        <div class="topActions">
          <span class="chipStatus">${state.health?.ffmpeg ? "RENDER LOCAL" : "ENGINE OFFLINE"}</span>
          <button class="iconBtn" data-open-settings title="设置">${icon("settings")}</button>
        </div>
      </div>

      <div class="studioTop">
        <div>
          <a href="/" class="backLink" data-link>${icon("back")} 返回片库</a>
          <div class="studioTitleRow">
            <h1 class="studioTitle">${esc(p.title)}</h1>
            <span class="statusBadge ${statusClass}">${statusText}</span>
          </div>
          <p class="studioLogline">${esc(p.logline || p.premise)}</p>
        </div>
        <div class="studioActions">
          ${(p.episodes || []).length > 1 ? `<select class="select" id="episodeSelect">${(p.episodes || []).map((e) => `<option value="${e.index}" ${e.index === ep.index ? "selected" : ""}>第 ${String(e.index).padStart(2, "0")} 集 · ${esc(e.title)}</option>`).join("")}</select>` : ""}
          <button class="btn ghost small" data-next-episode>${icon("plus")} 生成下一集</button>
        </div>
      </div>

      <div class="studioGrid">
        <div class="playerCard">
          <div class="playerHead"><span>PREVIEW / 9:16</span><b>${hasVideo ? "FINAL CUT" : "WORK IN PROGRESS"}</b></div>
          <div class="stage" id="stage">
            ${video}
            ${!hasVideo && !ep.cover ? `<div class="stageOverlay"><span class="micro">MANJU ORIGINAL · EP.${String(ep.index).padStart(2, "0")}</span><h3>${esc(p.title)}</h3><p>${esc(ep.title || "")}</p></div>` : ""}
          </div>
          <div class="playerFoot">
            <span>${hasVideo ? `${fmtDuration(ep.duration)} · 720×1280 · 24FPS` : `${shots.length} 镜头 · 等待合成`}</span>
            <span>${hasVideo ? `<a href="${esc(ep.video)}" download>下载 MP4 ${icon("download")}</a>` : `${artCount}/${shots.length} 面板`}</span>
          </div>
        </div>

        <div class="workPanel">
          <div class="workCard head">
            <div>
              <div class="micro">EPISODE ${String(ep.index).padStart(2, "0")} / PRODUCTION</div>
              <h4>${esc(ep.title || "未命名")}</h4>
              <p>${esc(ep.summary || p.premise)}</p>
            </div>
            <span class="statusBadge ${statusClass}">${busy ? `${Math.round(job.progress || 0)}%` : outdated ? "STALE" : hasVideo ? `${fmtDuration(ep.duration)}` : "DRAFT"}</span>
          </div>

          <div class="workCard">
            <div class="steps">
              <div class="step done"><span class="stepNo">01</span><span class="stepName">剧本与人物小传</span><span class="stepState">READY</span></div>
              <div class="step done"><span class="stepNo">02</span><span class="stepName">8 镜分镜拆解</span><span class="stepState">${shots.length} SHOTS</span></div>
              <div class="step ${artCount === shots.length && shots.length ? "done" : stepActive("art")}"><span class="stepNo">03</span><span class="stepName">漫画面板绘制</span><span class="stepState">${artCount}/${shots.length}</span></div>
              <div class="step ${busy && (job.stage === "voice" || job.stage === "music") ? "active" : hasVideo ? "done" : ""}"><span class="stepNo">04</span><span class="stepName">角色配音与氛围配乐</span><span class="stepState">${hasVideo ? "MIXED" : busy ? "WORKING" : "PENDING"}</span></div>
              <div class="step ${busy && job.stage === "frames" ? "active" : hasVideo && !outdated ? "done" : ""}"><span class="stepNo">05</span><span class="stepName">运镜、气泡与 MP4 合成</span><span class="stepState">${busy ? "ENCODING" : outdated ? "STALE" : hasVideo ? "READY" : "PENDING"}</span></div>
            </div>
            <div class="renderBox">
              <select class="select resSelect" id="resSelect">
                <option value="720p" ${p.resolution !== "1080p" ? "selected" : ""}>720 × 1280 · 快速</option>
                <option value="1080p" ${p.resolution === "1080p" ? "selected" : ""}>1080 × 1920 · 高清</option>
              </select>
              <button class="btn small" data-action="render" ${busy ? "disabled" : ""}>${busy ? "制作中" : "开始制作"}</button>
            </div>
            <p class="renderHint">${artEngine === "comfyui" ? "AI 插画模式 · 首次会先生成角色参考，再逐镜用 IP-Adapter 绘制；ComfyUI 不可用时会自动回退本地剪影。" : "含 8 个漫画面板、中文配音、程序化配乐与字幕。首次约 1–3 分钟，本机完成。"}${p.sample && artEngine === "comfyui" ? " 现有样片保留剪影版，重新渲染会切换为 AI 插画。" : ""}</p>
            <div class="progressWrap ${busy || job?.status === "failed" ? "show" : ""}" id="progressWrap">
              <div class="progressLine"><i id="progressFill" style="width:${busy ? job.progress || 0 : 0}%"></i></div>
              <div class="progressMeta"><span id="progressMsg">${busy ? esc(job.message || "") : ""}</span><b id="progressPct">${busy ? `${Math.round(job.progress || 0)}%` : ""}</b></div>
              <div class="jobError ${job?.status === "failed" ? "show" : ""}" id="jobError">${job?.status === "failed" ? esc(job.error || "制作失败") : ""}</div>
            </div>
            <div class="actionRow">
              ${hasVideo ? `<a class="btn ghost small" href="${esc(ep.video)}" download>${icon("download")} 成片</a>` : ""}
              ${hasVideo ? `<a class="btn ghost small" href="${esc(ep.srt || "#")}" download>SRT 字幕</a>` : ""}
              ${hasVideo ? `<a class="btn ghost small" href="${esc(ep.cover || "#")}" download>封面</a>` : ""}
            </div>
          </div>

          <div class="workGrid">
            <div class="workCard tight">
              <div class="micro">CAST / 角色</div>
              <h4>出场人物</h4>
              <div class="characters" style="margin-top:12px">${charChips || '<span class="hint">暂无角色</span>'}</div>
            </div>
            <div class="workCard tight">
              <div class="micro">SHEET / 制作单</div>
              <h4>本集参数</h4>
              <div class="kv"><span>画幅</span><b>9:16 竖屏</b></div>
              <div class="kv"><span>风格</span><b>${esc(style.name)}</b></div>
              <div class="kv"><span>画面</span><b>${artEngine === "comfyui" ? "ComfyUI · IP-Adapter" : "本地剪影"}</b></div>
              <div class="kv"><span>配音</span><b>${state.config?.tts?.engine === "local" ? "macOS 本地" : "Edge 免费"}</b></div>
              <div class="kv"><span>更新</span><b>${fmtDate(p.updated_at)}</b></div>
            </div>
          </div>
        </div>
      </div>

      <div class="tabs">
        <button class="tabBtn ${state.tab === "story" ? "active" : ""}" data-tab="story">分镜板 <span>${shots.length}</span></button>
        <button class="tabBtn ${state.tab === "script" ? "active" : ""}" data-tab="script">本集剧本</button>
        <button class="tabBtn ${state.tab === "notes" ? "active" : ""}" data-tab="notes">导演笔记</button>
      </div>
      <div class="storyView ${state.tab !== "story" ? "hide" : ""}" id="storyView">
        <div class="storyGrid">${shotCards}</div>
      </div>
      <div class="scriptView ${state.tab === "script" ? "show" : ""}" id="scriptView">
        <div class="scriptPaper">
          <h2>${esc(p.title)}</h2>
          <div class="meta">第 ${String(ep.index).padStart(2, "0")} 集 · ${esc(ep.title || "")}　/　${esc(p.genre || "")}　/　${esc(style.tag)}</div>
          ${script}
        </div>
      </div>
      <div class="scriptView ${state.tab === "notes" ? "show" : ""}" id="notesView">
        <div class="workCard" style="max-width:760px;margin:0 auto">
          <div class="micro">DIRECTOR'S NOTE</div>
          <h4>这一集在讲什么</h4>
          <p style="font-size:13px;line-height:2;margin-top:12px">${esc(ep.summary || p.logline || "")}</p>
          <div class="kv" style="margin-top:14px"><span>结尾钩子</span><b style="font-family:var(--sans);max-width:70%;text-align:right">${esc(ep.hook || "—")}</b></div>
          <p class="renderHint" style="margin-top:18px">提示：点击任意分镜可以修改旁白、台词和运镜。保存后重新生成本集，改动会进入成片。</p>
        </div>
      </div>`;

    bindStudio();
    if (busy) updateJobUI(job);
  }

  function bindStudio() {
    const p = state.project;
    const ep = currentEpisode();
    $$("[data-open-settings]").forEach((el) => el.addEventListener("click", () => openSettings()));
    $$("[data-action=render]").forEach((el) => el.addEventListener("click", startRender));
    $$("[data-shot]").forEach((el) => el.addEventListener("click", () => openShotEditor(el.dataset.shot)));
    $$("[data-tab]").forEach((el) => el.addEventListener("click", () => {
      state.tab = el.dataset.tab;
      $$("[data-tab]").forEach((b) => b.classList.toggle("active", b === el));
      $("#storyView")?.classList.toggle("hide", state.tab !== "story");
      $("#scriptView")?.classList.toggle("show", state.tab === "script");
      $("#notesView")?.classList.toggle("show", state.tab === "notes");
    }));
    const select = $("#episodeSelect");
    if (select) select.addEventListener("change", () => {
      state.episodeIndex = Number(select.value);
      state.tab = "story";
      renderStudio();
    });
    $("[data-next-episode]")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        const data = await api(`/api/projects/${p.id}/episodes/generate`, { method: "POST" });
        state.project = data.project;
        state.episodeIndex = data.episode.index;
        state.tab = "story";
        toast(`第 ${data.episode.index} 集已生成，开始制作吧`);
        renderStudio();
      } catch (err) {
        toast(err.message, "error");
      } finally { btn.disabled = false; }
    });
    $$(".stage video, .stagePlay").forEach((el) => el.addEventListener("click", (ev) => {
      if (ev.target.closest("video")) return;
      const video = $(".stage video");
      if (video) video.play();
      else if (ep.video) {
        const stage = $("#stage");
        stage.innerHTML = `<video controls autoplay playsinline src="${esc(ep.video)}" poster="${esc(ep.cover || "")}"></video>`;
      } else if (state.job) toast("本集正在生成，请稍候");
      else startRender();
    }));
  }

  // ---------------------------------------------------------------------
  // render job
  // ---------------------------------------------------------------------
  async function startRender() {
    const p = state.project;
    const ep = currentEpisode();
    if (!p || !ep) return;
    if (state.job && (state.job.status === "running" || state.job.status === "queued")) {
      toast("本集正在生成中"); return;
    }
    const resolution = $("#resSelect")?.value || p.resolution || "720p";
    $$("[data-action=render]").forEach((b) => { b.disabled = true; b.textContent = "准备中…"; });
    try {
      const data = await api(`/api/projects/${p.id}/episodes/${ep.index}/render`, { method: "POST", body: { resolution } });
      state.job = data.job;
      sessionStorage.setItem(`manju_job_${p.id}`, data.job.id);
      $$(".statusBadge").forEach((b) => { b.textContent = "生成中"; b.className = "statusBadge working"; });
      if ($("#progressWrap")) $("#progressWrap").classList.add("show");
      updateJobUI(state.job);
      startPolling();
      toast("开始生成。可以留在这个页面看进度。");
    } catch (err) {
      toast(err.message, "error");
      $$("[data-action=render]").forEach((b) => { b.disabled = false; b.innerHTML = `${icon("spark")} 生成本集`; });
    }
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(pollJob, 850);
  }

  function stopPolling() {
    if (state.pollTimer) clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  async function pollJob() {
    if (!state.job || !state.project) return;
    try {
      const data = await api(`/api/jobs/${state.job.id}`);
      const job = data.job;
      state.job = job;
      updateJobUI(job);
      if (job.status === "done") {
        stopPolling();
        sessionStorage.removeItem(`manju_job_${state.project.id}`);
        const pdata = await api(`/api/projects/${state.project.id}`);
        state.project = pdata.project;
        state.job = null;
        toast("成片好了。");
        renderStudio();
        $(".stage video")?.scrollIntoView({ behavior: "smooth", block: "center" });
      } else if (job.status === "failed") {
        stopPolling();
        sessionStorage.removeItem(`manju_job_${state.project.id}`);
        state.job = job;
        renderStudio();
        toast(`制作失败：${(job.error || "未知错误").slice(0, 120)}`, "error");
      }
    } catch (err) {
      stopPolling();
      toast(err.message, "error");
    }
  }

  function updateJobUI(job) {
    const fill = $("#progressFill");
    const pct = $("#progressPct");
    const msg = $("#progressMsg");
    const err = $("#jobError");
    if (fill) fill.style.width = `${Math.max(0, Math.min(100, job.progress || 0))}%`;
    if (pct) pct.textContent = `${Math.round(job.progress || 0)}%`;
    if (msg) msg.textContent = job.message || (job.status === "queued" ? "排队中" : "生成中");
    if (err) {
      err.classList.toggle("show", job.status === "failed");
      err.textContent = job.error || "";
    }
    const wrap = $("#progressWrap");
    if (wrap) wrap.classList.add("show");
    if (job.status === "running" || job.status === "queued") {
      $$(".statusBadge").forEach((b) => { b.textContent = "生成中"; b.className = "statusBadge working"; });
    }
    $$(".step").forEach((el, idx) => {
      if (idx === 0 || idx === 1) return;
      el.classList.remove("active", "done");
      const order = { art: 2, voice: 3, music: 3, frames: 4, encode: 4, finalize: 4, done: 5 };
      const now = order[job.stage] || 0;
      if (now > idx) el.classList.add("done");
      else if (now === idx) el.classList.add("active");
    });
  }

  // ---------------------------------------------------------------------
  // shot editor
  // ---------------------------------------------------------------------
  function openShotEditor(shotId) {
    const ep = currentEpisode();
    const shot = ep.shots.find((s) => s.id === shotId);
    if (!shot) return;
    const dialogues = JSON.parse(JSON.stringify(shot.dialogues || []));
    let html = `
      <div class="modalHead">
        <div>
          <div class="micro">SHOT ${String(shot.index).padStart(2, "0")} / EDIT</div>
          <h3>修改这一镜</h3>
          <p>改的是剧本层。保存后重新生成，才会进入成片。</p>
        </div>
        <button class="modalClose" data-close>${icon("close")}</button>
      </div>
      <div class="modalBody">
        <div class="fieldRow">
          <div class="field"><label>地点</label><input class="input" id="shotLocation" value="${esc(shot.location || "")}" /></div>
          <div class="field"><label>时间</label><input class="input" id="shotTime" value="${esc(shot.time || "")}" /></div>
        </div>
        <div class="fieldRow">
          <div class="field"><label>景别</label>
            <select id="shotType">
              ${["wide", "medium", "close", "detail"].map((v) => `<option value="${v}" ${shot.shot_type === v ? "selected" : ""}>${{ wide: "远景 Wide", medium: "中景 Medium", close: "特写 Close", detail: "细节 Detail" }[v]}</option>`).join("")}
            </select>
          </div>
          <div class="field"><label>运镜</label>
            <select id="shotCamera">
              ${["缓推", "横移", "急推", "固定", "微距", "手持跟拍", "环绕"].map((v) => `<option value="${v}" ${shot.camera === v ? "selected" : ""}>${v}</option>`).join("")}
            </select>
          </div>
        </div>
        <div class="field">
          <label>旁白 / 内心独白 <span>可留空</span></label>
          <textarea class="textarea" id="shotNarration" style="min-height:64px">${esc(shot.narration || "")}</textarea>
        </div>
        <div class="field">
          <label>AI 插画提示词 <span>追加，可选</span></label>
          <textarea class="textarea" id="shotImagePrompt" style="min-height:62px" placeholder="例：低机位，雨水打在镜头上，人物只占画面三分之一">${esc(shot.image_prompt || "")}</textarea>
          <p class="hint">仅在画面引擎为 ComfyUI + IP-Adapter 时生效，会追加到自动生成的角色 / 场景提示词之后。</p>
        </div>
        <div class="field">
          <label>对白 <span>最多 3 句</span></label>
          <div id="dialogList"></div>
          <button class="addLine" id="addDialogue">+ 添加一句对白</button>
        </div>
        <div class="field">
          <label>画面角标</label>
          <input class="input" id="shotCaption" value="${esc(shot.caption || "")}" />
          <p class="hint">会在漫画面板的左上角出现。留空则不显示。</p>
        </div>
      </div>
      <div class="modalFoot">
        <button class="btn ghost" data-close>取消</button>
        <button class="btn" id="saveShot">${icon("edit")} 保存修改</button>
      </div>`;
    openModal(html);

    const renderRows = () => {
      $("#dialogList").innerHTML = dialogues.map((d, i) => `
        <div class="dialogRow">
          <input class="input" data-dlg="speaker" data-i="${i}" value="${esc(d.speaker || "")}" placeholder="角色名" />
          <input class="input" data-dlg="text" data-i="${i}" value="${esc(d.text || "")}" placeholder="台词" />
          <select class="input emotionInput" data-dlg="emotion" data-i="${i}">
            ${EMOTIONS.map((em) => `<option value="${em}" ${d.emotion === em ? "selected" : ""}>${em}</option>`).join("")}
          </select>
          <button class="iconTiny" data-remove="${i}" title="删除">${icon("close")}</button>
        </div>`).join("") || `<p class="hint" style="margin:0 0 8px">还没有对白，添加一句吧。</p>`;
      $$("#dialogList [data-dlg]").forEach((input) => input.addEventListener("input", () => {
        const i = Number(input.dataset.i);
        dialogues[i][input.dataset.dlg] = input.value;
      }));
      $$("#dialogList [data-remove]").forEach((btn) => btn.addEventListener("click", () => {
        dialogues.splice(Number(btn.dataset.remove), 1);
        renderRows();
      }));
    };
    renderRows();
    $("#addDialogue").addEventListener("click", () => {
      if (dialogues.length >= 3) { toast("单镜最多 3 句对白"); return; }
      dialogues.push({ speaker: state.project.characters?.[0]?.name || "", text: "", emotion: "冷淡" });
      renderRows();
    });
    $("#saveShot").addEventListener("click", async () => {
      const btn = $("#saveShot");
      btn.disabled = true;
      try {
        const body = {
          location: $("#shotLocation").value.trim(),
          time: $("#shotTime").value.trim(),
          shot_type: $("#shotType").value,
          camera: $("#shotCamera").value,
          narration: $("#shotNarration").value.trim(),
          image_prompt: $("#shotImagePrompt").value.trim(),
          caption: $("#shotCaption").value.trim(),
          dialogues: dialogues.filter((d) => d.text && d.text.trim()),
        };
        const data = await api(`/api/projects/${state.project.id}/episodes/${ep.index}/shots/${shot.id}`, { method: "PATCH", body });
        state.project = data.project;
        closeModal();
        renderStudio();
        toast("已保存。重新生成本集后进入成片。");
      } catch (err) {
        btn.disabled = false;
        toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------------
  // settings
  // ---------------------------------------------------------------------
  async function openSettings(direct = false) {
    try {
      const [settings, health] = await Promise.all([api("/api/settings"), api("/api/health")]);
      state.config = settings.config;
      state.health = health;
      const cfg = settings.config;
      openModal(`
        <div class="modalHead">
          <div>
            <div class="micro">LOCAL CONFIG / 本机</div>
            <h3>本地设置</h3>
            <p>没有 API Key 也能出片。这里只决定用哪套本地 / 免费引擎。</p>
          </div>
          <button class="modalClose" data-close>${icon("close")}</button>
        </div>
        <div class="modalBody">
          <div class="settingsSection">
            <div class="micro">01 / CAPABILITIES</div>
            <h4>引擎自检</h4>
            <div class="kv"><span>视频合成 · FFmpeg</span><b style="color:${health.ffmpeg ? "var(--teal)" : "var(--red)"}">${health.ffmpeg ? "已就绪" : "未找到"}</b></div>
            <div class="kv"><span>免费中文配音 · Edge TTS</span><b style="color:var(--teal)">已就绪</b></div>
            <div class="kv"><span>离线备用 · macOS say</span><b style="color:${health.macos_say ? "var(--teal)" : "var(--muted)"}">${health.macos_say ? "已就绪" : "不可用"}</b></div>
            <div class="kv"><span>画面引擎</span><b>${cfg.art.engine === "comfyui" ? "ComfyUI + IP-Adapter" : "本地程序化绘制"}</b></div>
            <div class="kv"><span>剧本引擎</span><b>${cfg.llm.enabled ? "Ollama / 兼容 LLM" : "内置导演（离线）"}</b></div>
          </div>

          <div class="settingsSection">
            <div class="micro">02 / VOICE</div>
            <h4>配音</h4>
            <div class="fieldRow">
              <div class="field"><label>主要引擎</label>
                <select id="ttsEngine">
                  <option value="edge" ${cfg.tts.engine === "edge" ? "selected" : ""}>Edge TTS · 免费在线</option>
                  <option value="local" ${cfg.tts.engine === "local" ? "selected" : ""}>macOS say · 完全离线</option>
                </select>
              </div>
              <div class="field"><label>旁白声线</label>
                <select id="narratorVoice">
                  ${VOICES.map(([id, name]) => `<option value="${id}" ${cfg.tts.narrator_voice === id ? "selected" : ""}>${name}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="switchRow">
              <div><b>网络失败时改用本机语音</b><small>macOS Tingting 离线声线，自动对男声做低音处理。</small></div>
              <label class="switch"><input type="checkbox" id="fallbackLocal" ${cfg.tts.fallback_local ? "checked" : ""} /><i></i></label>
            </div>
          </div>

          <div class="settingsSection">
            <div class="micro">03 / STORY MODEL</div>
            <h4>Ollama / 兼容大模型 <span style="font-family:var(--mono);font-size:8px;color:var(--muted)">OPTIONAL</span></h4>
            <div class="switchRow">
              <div><b>启用 LLM 写剧本</b><small>支持 Ollama、LM Studio、DeepSeek 等 OpenAI 兼容接口。关闭时用内置导演引擎。</small></div>
              <label class="switch"><input type="checkbox" id="llmEnabled" ${cfg.llm.enabled ? "checked" : ""} /><i></i></label>
            </div>
            <div class="fieldRow" style="margin-top:14px">
              <div class="field"><label>Base URL</label><input class="input" id="llmBase" value="${esc(cfg.llm.base_url)}" placeholder="http://127.0.0.1:11434/v1" /></div>
              <div class="field"><label>Model</label><input class="input" id="llmModel" value="${esc(cfg.llm.model)}" placeholder="qwen2.5:3b" /></div>
            </div>
            <div class="field"><label>API Key <span>本地 Ollama 可留空</span></label><input class="input" id="llmKey" type="password" value="${esc(cfg.llm.api_key || "")}" placeholder="${cfg.llm.has_key ? "已保存，留空保持不变" : "sk-..."}" /></div>
            <div class="actionRow">
              <button class="btn ghost small" id="refreshModels">${icon("refresh")} 读取模型列表</button>
              <button class="btn ghost small" id="testLlm">测试连接</button>
              <span class="testResult" id="testResult"></span>
            </div>
            <select class="select" id="llmModelSelect" style="display:none;margin-top:9px"></select>
            <p class="hint">Ollama 启动后执行 <code>ollama pull qwen2.5:3b</code>；Base URL 填 <code>http://127.0.0.1:11434/v1</code>。没有 LLM 时可随时用内置导演引擎。</p>
          </div>

          <div class="settingsSection">
            <div class="micro">04 / ART ENGINE</div>
            <h4>分镜插画 <span style="font-family:var(--mono);font-size:8px;color:var(--muted)">COMFYUI + IP-ADAPTER</span></h4>
            <div class="fieldRow">
              <div class="field"><label>画面引擎</label>
                <select id="artEngine">
                  <option value="builtin" ${cfg.art.engine !== "comfyui" ? "selected" : ""}>内置霓虹剪影 · 零依赖</option>
                  <option value="comfyui" ${cfg.art.engine === "comfyui" ? "selected" : ""}>ComfyUI + IP-Adapter · AI 插画</option>
                </select>
              </div>
              <div class="field"><label>ComfyUI 地址</label><input class="input" id="comfyUrl" value="${esc(cfg.art.comfyui_url || "http://127.0.0.1:8188")}" placeholder="http://127.0.0.1:8188" /></div>
            </div>
            <div id="comfyFields" style="display:${cfg.art.engine === "comfyui" ? "block" : "none"}">
              <div class="fieldRow">
                <div class="field"><label>Checkpoint</label><select id="comfyCheckpoint"><option value="${esc(cfg.art.checkpoint || "")}">${esc(cfg.art.checkpoint || "检测后选择 / 自动")}</option></select></div>
                <div class="field"><label>IP-Adapter 预设</label><select id="comfyPreset">
                  ${["PLUS (high strength)", "PLUS FACE (portraits)", "STANDARD (medium strength)", "LIGHT - SD1.5 only (low strength)"].map((p) => `<option value="${p}" ${cfg.art.preset === p ? "selected" : ""}>${p}</option>`).join("")}
                </select></div>
              </div>
              <div class="fieldRow">
                <div class="field"><label>Steps</label><input class="input" id="comfySteps" type="number" min="4" max="60" value="${Number(cfg.art.steps || 24)}" /></div>
                <div class="field"><label>CFG</label><input class="input" id="comfyCfg" type="number" min="1" max="20" step="0.5" value="${Number(cfg.art.cfg || 7)}" /></div>
              </div>
              <div class="fieldRow">
                <div class="field"><label>IP-Adapter 权重</label><input class="input" id="comfyWeight" type="number" min="0" max="2" step="0.05" value="${Number(cfg.art.ipadapter_weight || 0.62)}" /></div>
                <div class="field"><label>权重类型</label><select id="comfyWeightType">
                  ${["prompt is more important", "standard", "style transfer"].map((v) => `<option value="${v}" ${(cfg.art.ipadapter_weight_type || "prompt is more important") === v ? "selected" : ""}>${v}</option>`).join("")}
                </select></div>
              </div>
              <div class="fieldRow">
                <div class="field"><label>生成尺寸</label><select id="comfySize">
                  <option value="512x896" ${Number(cfg.art.width) !== 768 ? "selected" : ""}>512 × 896 · SD1.5</option>
                  <option value="768x1344" ${Number(cfg.art.width) === 768 ? "selected" : ""}>768 × 1344 · SDXL</option>
                </select></div>
                <div class="field"><label>参考图缓存</label><div class="hint" style="margin-top:10px">在 <code>data/projects/&lt;id&gt;/refs/</code></div></div>
              </div>
              <div class="actionRow"><button class="btn ghost small" id="testComfy">${icon("refresh")} 测试 ComfyUI / 读取模型</button><span class="testResult" id="comfyResult"></span></div>
              <p class="hint">需要 ComfyUI + <code>ComfyUI_IPAdapter_plus</code> 自定义节点。首次渲染会为每个角色生成一张参考图，之后每镜用 IP-Adapter 锁定角色。失败会自动回退本地剪影，不会中断成片。</p>
            </div>
            <p class="hint" id="builtinArtHint" style="display:${cfg.art.engine === "comfyui" ? "none" : "block"}">当前使用内置矢量引擎：剪影、霓虹、雨、网点与漫画角标，零依赖、零成本。</p>
          </div>
        </div>
        <div class="modalFoot">
          <button class="btn ghost" data-close>取消</button>
          <button class="btn" id="saveSettings">保存设置</button>
        </div>`, "wide");

      const syncArtFields = () => {
        const comfy = $("#artEngine").value === "comfyui";
        $("#comfyFields").style.display = comfy ? "block" : "none";
        $("#builtinArtHint").style.display = comfy ? "none" : "block";
      };
      $("#artEngine").addEventListener("change", syncArtFields);
      $("#testLlm").addEventListener("click", async () => {
        const el = $("#testResult");
        el.className = "testResult";
        el.textContent = "连接中…";
        try {
          const r = await api("/api/settings/test-llm", { method: "POST", body: {
            base_url: $("#llmBase").value.trim(),
            model: $("#llmModel").value.trim(),
            api_key: $("#llmKey").value.trim(),
          } });
          el.className = `testResult ${r.ok ? "ok" : "fail"}`;
          el.textContent = r.message;
        } catch (err) { el.className = "testResult fail"; el.textContent = err.message; }
      });
      $("#refreshModels").addEventListener("click", async () => {
        const el = $("#testResult");
        const key = $("#llmKey").value.trim();
        el.className = "testResult";
        el.textContent = "读取模型列表…";
        try {
          const q = new URLSearchParams({ base_url: $("#llmBase").value.trim() });
          if (key && !key.includes("•")) q.set("api_key", key);
          const r = await api(`/api/llm/models?${q.toString()}`);
          const sel = $("#llmModelSelect");
          if (!r.ok) {
            el.className = "testResult fail";
            el.textContent = "没有读到模型。请确认 Ollama / 兼容服务已启动。";
            sel.style.display = "none";
            return;
          }
          sel.innerHTML = r.models.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
          sel.style.display = "block";
          if (!$("#llmModel").value.trim() || !r.models.includes($("#llmModel").value.trim())) $("#llmModel").value = r.models[0];
          sel.value = $("#llmModel").value;
          el.className = "testResult ok";
          el.textContent = `找到 ${r.models.length} 个模型 · ${r.source || "API"}`;
        } catch (err) { el.className = "testResult fail"; el.textContent = err.message; }
      });
      $("#llmModelSelect").addEventListener("change", (e) => { $("#llmModel").value = e.target.value; });
      $("#testComfy").addEventListener("click", async () => {
        const el = $("#comfyResult");
        el.className = "testResult";
        el.textContent = "连接中…";
        try {
          const r = await api(`/api/comfy/status?url=${encodeURIComponent($("#comfyUrl").value.trim())}`);
          if (!r.ok) {
            el.className = "testResult fail";
            el.textContent = r.message || "连接失败";
            return;
          }
          const sel = $("#comfyCheckpoint");
          const current = sel.value;
          sel.innerHTML = r.checkpoints.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("") || '<option value="">没有 checkpoint</option>';
          if (current && r.checkpoints.includes(current)) sel.value = current;
          else if (r.checkpoint && r.checkpoints.includes(r.checkpoint)) sel.value = r.checkpoint;
          el.className = `testResult ${r.ipadapter_ready ? "ok" : "fail"}`;
          el.textContent = r.ipadapter_ready
            ? `已连接 · ${r.checkpoints.length} 个 checkpoint · IP-Adapter 就绪`
            : "已连接，但缺少 IPAdapterUnifiedLoader / IPAdapter 节点";
        } catch (err) { el.className = "testResult fail"; el.textContent = err.message; }
      });
      $("#saveSettings").addEventListener("click", async () => {
        const btn = $("#saveSettings");
        btn.disabled = true;
        try {
          const body = {
            tts: {
              engine: $("#ttsEngine").value,
              narrator_voice: $("#narratorVoice").value,
              fallback_local: $("#fallbackLocal").checked,
            },
            llm: {
              enabled: $("#llmEnabled").checked,
              base_url: $("#llmBase").value.trim(),
              model: $("#llmModel").value.trim(),
              api_key: $("#llmKey").value.trim(),
            },
            art: {
              engine: $("#artEngine").value,
              comfyui_url: $("#comfyUrl").value.trim(),
              checkpoint: $("#comfyCheckpoint").value,
              preset: $("#comfyPreset").value,
              steps: Number($("#comfySteps").value) || 24,
              cfg: Number($("#comfyCfg").value) || 7,
              ipadapter_weight: Number($("#comfyWeight").value) || 0.62,
              ipadapter_weight_type: $("#comfyWeightType").value,
              width: Number(($("#comfySize").value || "512x896").split("x")[0]),
              height: Number(($("#comfySize").value || "512x896").split("x")[1]),
            },
          };
          const r = await api("/api/settings", { method: "PUT", body });
          state.config = r.config;
          state.health = await api("/api/health");
          toast("设置已保存");
          closeModal();
          if (direct) navigate("/");
        } catch (err) {
          btn.disabled = false;
          toast(err.message, "error");
        }
      });
    } catch (err) { toast(err.message, "error"); }
  }

  function openAssets() {
    const p = state.project;
    if (!p) {
      const all = state.projects;
      openModal(`
        <div class="modalHead"><div><div class="micro">ASSET LIBRARY</div><h3>素材与角色</h3><p>每个项目的角色、画面和音频都独立保存在本机。</p></div><button class="modalClose" data-close>${icon("close")}</button></div>
        <div class="modalBody">
          <div class="emptyState"><strong>先打开一部漫剧</strong>角色卡、分镜面板和音频素材会跟随项目出现。<br/><br/><button class="btn small" data-close>去看看项目</button></div>
          <p class="hint" style="margin-top:16px">当前片库：${all.length} 个项目 · 全部数据位于 <code>data/projects/</code></p>
        </div>`);
      return;
    }
    const chars = (p.characters || []).map((c) => `<div class="workCard tight" style="margin-bottom:10px"><div class="micro">${esc(c.role || "CHARACTER")}</div><h4 style="font-size:20px;margin-top:4px">${esc(c.name)}</h4>${c.ref_url ? `<img src="${esc(c.ref_url)}" alt="${esc(c.name)} 参考图" style="width:100%;max-height:280px;object-fit:cover;margin:10px 0;border:1px solid var(--line2)" />` : ""}<p style="font-size:11px;color:var(--muted);line-height:1.8">${esc(c.persona || "")}</p><div class="kv"><span>外形</span><b style="font-family:var(--sans);text-align:right;max-width:70%">${esc(c.appearance || "")}</b></div><div class="kv"><span>参考图 · IP-Adapter</span><b style="color:${c.ref_url ? "var(--teal)" : "var(--muted2)"}">${c.ref_url ? "已生成" : "尚未生成"}</b></div><div class="kv"><span>声线</span><b>${esc((c.voice || "").replace("zh-CN-", "").replace("Neural", ""))}</b></div></div>`).join("");
    openModal(`
      <div class="modalHead"><div><div class="micro">ASSET LIBRARY / ${esc(p.title)}</div><h3>素材与角色</h3><p>角色锚点决定跨镜头的形象一致性。</p></div><button class="modalClose" data-close>${icon("close")}</button></div>
      <div class="modalBody"><div class="settingsSection"><div class="micro">CAST / ${(p.characters || []).length}</div>${chars || '<p class="hint">暂无角色</p>'}</div>
      <div class="settingsSection"><div class="micro">MEDIA</div><div class="kv"><span>分镜面板</span><b>${(currentEpisode()?.shots || []).filter((s) => s.image_url).length} 张 · 1080×1920</b></div><div class="kv"><span>配音</span><b>${currentEpisode()?.video ? "已生成" : "等待制作"}</b></div><div class="kv"><span>配乐</span><b>程序化生成 · 48kHz</b></div></div></div>`, "narrow");
  }

  // ---------------------------------------------------------------------
  // modal
  // ---------------------------------------------------------------------
  function openModal(html, cls = "") {
    const root = $("#modalRoot");
    root.innerHTML = `<div class="modalBackdrop" data-close></div><div class="modalPanel ${cls}">${html}</div>`;
    root.classList.add("open");
    document.body.style.overflow = "hidden";
    $$("[data-close]", root).forEach((el) => el.addEventListener("click", closeModal));
    document.addEventListener("keydown", escClose);
    // focus first meaningful input
    setTimeout(() => { const input = $(".modalPanel textarea, .modalPanel input:not([type=checkbox])"); if (input) input.focus({ preventScroll: true }); }, 100);
  }
  function escClose(e) { if (e.key === "Escape") closeModal(); }
  function closeModal() {
    const root = $("#modalRoot");
    root.classList.remove("open");
    root.innerHTML = "";
    document.body.style.overflow = "";
    document.removeEventListener("keydown", escClose);
  }

  boot();
})();
