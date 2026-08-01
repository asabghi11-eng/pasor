/*!
 * worldcup-panel.js — Phase 12 UI for Hokm (زبان، منطقه و مسابقات جهانی).
 *
 * همون الگوی economy-panel.js / social-panel.js / tournament-panel.js /
 * monetization-panel.js / stats-panel.js: کاملاً مستقل، فقط با یک خط وصل میشه.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body>:
 *        <script src="worldcup-panel.js"></script>
 *   3) همون جایی که وب‌ساکت رو می‌سازی:
 *        HokmWorldCup.attach(ws);
 *
 * این پنل سه بخش داره:
 *   - زبان: سرور از این به بعد پیغام‌های خطا/toast رو به همون زبان برمی‌گردونه
 *     (بقیه‌ی رابط کاربری فعلاً فقط فارسیه — یک بازنویسی بزرگ‌تر می‌خواد).
 *   - منطقه: کوئیک‌مچ ترجیح میده تو رو با هم‌منطقه‌ای جفت کنه، و جدول
 *     امتیازات منطقه‌ای رو هم می‌شه از همینجا دید.
 *   - جام جهانی: ثبت‌نام فصلی، مرحله مقدماتی داخل منطقه، مرحله نهایی جهانی،
 *     و قهرمان فصل.
 */
(function () {
  "use strict";

  const CSS = `
  .hkw-fab {
    position: fixed; bottom: calc(176px + env(safe-area-inset-bottom)); inset-inline-end: calc(18px + env(safe-area-inset-right)); z-index: 9998;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #241a10, #402c14);
    border: 1px solid #e6b455; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #ffe9c2; user-select: none;
    transition: transform .15s ease;
  }
  @media (hover:hover) and (pointer:fine){ .hkw-fab:hover { transform: translateY(-2px); } }
  @media (max-width:640px){
    .hkw-fab{
      bottom: calc(256px + env(safe-area-inset-bottom));
      inset-inline-end: calc(10px + env(safe-area-inset-right));
      padding:6px 10px; gap:6px; font-size:12px;
    }
  }

  .hkw-overlay {
    position: fixed; inset: 0; background: rgba(6,10,12,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hkw-overlay.hkw-open { display: flex; }
  .hkw-modal {
    width: min(92vw, 480px); max-height: 86vh; overflow: hidden;
    background: #1a130c; border: 1px solid #e6b455; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #ffe9c2; direction: rtl;
  }
  .hkw-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #3a2a16; background: linear-gradient(135deg, #241a10, #1a130c); }
  .hkw-head h2 { margin: 0; font-size: 16px; }
  .hkw-close { cursor: pointer; font-size: 20px; line-height: 1; color: #d8b98a; background: none; border: none; width:44px; height:44px; display:flex; align-items:center; justify-content:center; margin:-10px; }
  .hkw-tabs { display: flex; border-bottom: 1px solid #3a2a16; }
  .hkw-tab { flex: 1; text-align: center; padding: 10px 4px; cursor: pointer; font-size: 13px; color: #a3855f; border-bottom: 2px solid transparent; background: none; border-top: none; border-inline: none; font-family: inherit; }
  .hkw-tab.hkw-active { color: #e6b455; border-bottom-color: #e6b455; }
  .hkw-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
  .hkw-panel { display: none; }
  .hkw-panel.hkw-active { display: block; }

  .hkw-note { color: #a3855f; font-size: 12px; text-align: center; padding: 20px 0; }

  .hkw-opt {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%; background: #241a10; border: 1px solid #3a2a16; border-radius: 10px;
    padding: 10px 12px; margin-bottom: 8px; cursor: pointer; color: #ffe9c2;
    font-family: inherit; font-size: 14px;
  }
  .hkw-opt.hkw-picked { border-color: #e6b455; background: rgba(230,180,85,.15); }
  .hkw-opt .hkw-check { color: #e6b455; font-weight: 700; visibility: hidden; }
  .hkw-opt.hkw-picked .hkw-check { visibility: visible; }

  .hkw-btn { width: 100%; border: none; border-radius: 8px; background: #e6b455; color: #1a130c; font-weight: 700; padding: 10px 12px; cursor: pointer; margin: 6px 0; font-family: inherit; }
  .hkw-btn:disabled { background: #3a2a16; color: #7d6647; cursor: not-allowed; }

  .hkw-status { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; background: rgba(230,180,85,.18); color: #e6b455; margin-bottom: 10px; }

  .hkw-card { background: #241a10; border-radius: 10px; padding: 10px; margin-bottom: 10px; text-align: center; }
  .hkw-champ { font-size: 15px; font-weight: 700; color: #ffd98a; }

  .hkw-row { display: flex; align-items: center; justify-content: space-between; padding: 7px 4px; border-bottom: 1px solid #3a2a16; font-size: 13px; }
  .hkw-row .hkw-rank { width: 22px; color: #a3855f; }
  .hkw-row.hkw-me { background: rgba(230,180,85,.12); border-radius: 6px; }
  .hkw-badge { border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; background: rgba(230,180,85,.15); color: #e6b455; }
  .hkw-badge.hkw-out { background: rgba(230,90,90,.18); color: #e65a5a; }

  .hkw-title-chip { display: inline-block; background: rgba(255,217,138,.15); color: #ffd98a; border-radius: 999px; padding: 2px 10px; font-size: 11px; margin: 2px 3px 2px 0; }
  `;

  function injectStyle() {
    const style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  // Fallback labels (Persian) used until the server's i18n_state arrives.
  const FALLBACK_STRINGS = {
    panel_title: "زبان، منطقه و جام جهانی",
    tab_language: "زبان",
    tab_region: "منطقه",
    tab_worldcup: "جام جهانی",
    region_leaderboard: "جدول امتیازات منطقه‌ای",
    worldcup_join: "ثبت‌نام در جام جهانی",
    worldcup_status_registration: "ثبت‌نام باز است",
    worldcup_status_qualifiers: "مرحله مقدماتی",
    worldcup_status_finals: "مرحله نهایی",
    worldcup_status_finished: "پایان‌یافته",
    worldcup_champion: "قهرمان فصل",
    worldcup_fab_label: "جهانی",
    worldcup_wins_suffix: "برد",
    worldcup_eliminated_badge: "حذف",
  };

  class WorldCupPanel {
    constructor() {
      this.ws = null;
      this.myPlayerId = null;
      this.strings = FALLBACK_STRINGS;
      this.languages = [];
      this.language = "fa";
      this.regions = [];
      this.region = "ir";
      this.worldCup = null;
      this.regionalLeaderboard = null;
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => this._send({ type: "get_world_cup" });
      if (ws.readyState === WebSocket.OPEN) request();
      ws.addEventListener("open", request);
      ws.addEventListener("message", (ev) => this._onMessage(ev));
    }

    _send(payload) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(payload));
    }

    _s(key) {
      return (this.strings && this.strings[key]) || FALLBACK_STRINGS[key] || key;
    }

    _onMessage(ev) {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      switch (msg.type) {
        case "login_ok":
          this.myPlayerId = msg.player_id;
          break;
        case "i18n_state":
          this.strings = msg.strings || FALLBACK_STRINGS;
          this.languages = msg.languages || [];
          this.language = msg.language || "fa";
          this._renderHead();
          this._renderLanguage();
          this._renderWorldCup();
          break;
        case "region_state":
          this.regions = msg.regions || [];
          this.region = msg.region || "ir";
          this._renderRegion();
          break;
        case "region_error":
        case "world_cup_error":
        case "worldcup_error":
          this._toast(msg.message);
          break;
        case "regional_leaderboard":
          this.regionalLeaderboard = msg;
          this._renderRegionalLeaderboard();
          break;
        case "world_cup_state":
          this.worldCup = msg;
          this._renderWorldCup();
          break;
        case "world_cup_eliminated":
          this._toast(msg.message);
          break;
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hkw-fab", "🌍 " + this._s("worldcup_fab_label"));
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hkw-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hkw-modal");
      modal.innerHTML = `
        <div class="hkw-head">
          <h2 class="hkw-title">🌍 ${this._s("panel_title")}</h2>
          <button class="hkw-close" type="button">×</button>
        </div>
        <div class="hkw-tabs">
          <button class="hkw-tab hkw-active" data-tab="language">${this._s("tab_language")}</button>
          <button class="hkw-tab" data-tab="region">${this._s("tab_region")}</button>
          <button class="hkw-tab" data-tab="worldcup">${this._s("tab_worldcup")}</button>
        </div>
        <div class="hkw-body">
          <div class="hkw-panel hkw-active" data-panel="language"></div>
          <div class="hkw-panel" data-panel="region"></div>
          <div class="hkw-panel" data-panel="worldcup"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);
      this.modal = modal;

      modal.querySelector(".hkw-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hkw-tab").forEach((tab) => tab.addEventListener("click", () => this._switchTab(tab.dataset.tab)));

      this.toastEl = el("div", "hkw-toast");
      Object.assign(this.toastEl.style, {
        position: "fixed", bottom: "180px", insetInlineEnd: "18px", zIndex: 10000,
        background: "#241a10", border: "1px solid #e6b455", color: "#ffe9c2",
        padding: "10px 16px", borderRadius: "10px", fontSize: "13px", maxWidth: "280px",
        opacity: 0, transform: "translateY(8px)", transition: "all .2s ease", pointerEvents: "none",
      });
      document.body.appendChild(this.toastEl);

      this._renderLanguage();
      this._renderRegion();
      this._renderWorldCup();
    }

    open() { this.overlay.classList.add("hkw-open"); }
    close() { this.overlay.classList.remove("hkw-open"); }

    _switchTab(name) {
      this.modal.querySelectorAll(".hkw-tab").forEach((t) => t.classList.toggle("hkw-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hkw-panel").forEach((p) => p.classList.toggle("hkw-active", p.dataset.panel === name));
    }

    _toast(text) {
      if (!text) return;
      this.toastEl.textContent = text;
      this.toastEl.style.opacity = 1;
      this.toastEl.style.transform = "translateY(0)";
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        this.toastEl.style.opacity = 0;
        this.toastEl.style.transform = "translateY(8px)";
      }, 4200);
    }

    _renderHead() {
      const title = this.modal.querySelector(".hkw-title");
      if (title) title.innerHTML = `🌍 ${this._s("panel_title")}`;
      const tabs = this.modal.querySelectorAll(".hkw-tab");
      if (tabs[0]) tabs[0].textContent = this._s("tab_language");
      if (tabs[1]) tabs[1].textContent = this._s("tab_region");
      if (tabs[2]) tabs[2].textContent = this._s("tab_worldcup");
    }

    _renderLanguage() {
      const panel = this.modal.querySelector('[data-panel="language"]');
      panel.innerHTML = "";
      if (!this.languages.length) {
        panel.appendChild(el("div", "hkw-note", "..."));
        return;
      }
      this.languages.forEach((lang) => {
        const opt = el("button", "hkw-opt" + (lang.key === this.language ? " hkw-picked" : ""));
        opt.type = "button";
        opt.innerHTML = `<span>${lang.flag || ""} ${lang.native}</span><span class="hkw-check">✓</span>`;
        opt.addEventListener("click", () => this._send({ type: "set_language", lang: lang.key }));
        panel.appendChild(opt);
      });
    }

    _renderRegion() {
      const panel = this.modal.querySelector('[data-panel="region"]');
      panel.innerHTML = "";
      if (!this.regions.length) {
        panel.appendChild(el("div", "hkw-note", "..."));
        return;
      }
      this.regions.forEach((region) => {
        const opt = el("button", "hkw-opt" + (region.key === this.region ? " hkw-picked" : ""));
        opt.type = "button";
        opt.innerHTML = `<span>${region.label}</span><span class="hkw-check">✓</span>`;
        opt.addEventListener("click", () => this._send({ type: "set_region", region: region.key }));
        panel.appendChild(opt);
      });

      const lbBtn = el("button", "hkw-btn", "🏆 " + this._s("region_leaderboard"));
      lbBtn.addEventListener("click", () => this._send({ type: "get_regional_leaderboard", region: this.region }));
      panel.appendChild(lbBtn);

      this._lbBox = el("div");
      panel.appendChild(this._lbBox);
      this._renderRegionalLeaderboard();
    }

    _renderRegionalLeaderboard() {
      if (!this._lbBox) return;
      this._lbBox.innerHTML = "";
      const data = this.regionalLeaderboard;
      if (!data || !data.top || !data.top.length) return;
      data.top.forEach((e, i) => {
        const row = el("div", "hkw-row" + (e.playerId === this.myPlayerId ? " hkw-me" : ""));
        row.innerHTML = `<span><span class="hkw-rank">${i + 1}.</span>${e.name || "?"}</span><span>${e.matchesWon ?? 0} ${this._s("worldcup_wins_suffix")}</span>`;
        this._lbBox.appendChild(row);
      });
    }

    _renderWorldCup() {
      const panel = this.modal.querySelector('[data-panel="worldcup"]');
      panel.innerHTML = "";
      const wc = this.worldCup;
      if (!wc) {
        panel.appendChild(el("div", "hkw-note", "..."));
        return;
      }

      const statusKey = "worldcup_status_" + wc.status;
      panel.appendChild(el("div", "hkw-status", this._s(statusKey)));

      if (wc.champion) {
        const champBox = el("div", "hkw-card");
        champBox.innerHTML = `<div class="hkw-champ">🏆 ${this._s("worldcup_champion")}: ${wc.champion}</div>`;
        panel.appendChild(champBox);
      }

      if (wc.myTitles && wc.myTitles.length) {
        const chips = el("div");
        wc.myTitles.forEach((title) => chips.appendChild(el("span", "hkw-title-chip", title)));
        panel.appendChild(chips);
      }

      if (!wc.myRegistered && wc.status === "registration") {
        const joinBtn = el("button", "hkw-btn", "🌍 " + this._s("worldcup_join"));
        joinBtn.disabled = !wc.eligible;
        joinBtn.addEventListener("click", () => this._send({ type: "join_world_cup" }));
        panel.appendChild(joinBtn);
        if (!wc.eligible) {
          panel.appendChild(el("div", "hkw-note", `${wc.totalRegistered ?? 0} / ${wc.minTotalToStart ?? "?"}`));
        }
      } else if (!wc.myRegistered) {
        panel.appendChild(el("div", "hkw-note", `${wc.totalRegistered ?? 0} / ${wc.minTotalToStart ?? "?"}`));
      }

      if (wc.standings && wc.standings.length) {
        wc.standings.forEach((s, i) => {
          const row = el("div", "hkw-row" + (s.playerId === this.myPlayerId ? " hkw-me" : ""));
          const badge = s.eliminated ? `<span class="hkw-badge hkw-out">${this._s("worldcup_eliminated_badge")}</span>` : `<span class="hkw-badge">${s.wins}-${s.losses}</span>`;
          row.innerHTML = `<span><span class="hkw-rank">${i + 1}.</span>${s.name}</span>${badge}`;
          panel.appendChild(row);
        });
      } else if (wc.myRegistered) {
        panel.appendChild(el("div", "hkw-note", "..."));
      }
    }
  }

  const instance = new WorldCupPanel();
  window.HokmWorldCup = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
