/*!
 * tournament-panel.js — Phase 8 UI for Hokm (تورنمنت/لیگ، جدول، لیدربورد جهانی).
 *
 * همون الگوی economy-panel.js / social-panel.js: کاملاً مستقل، فقط با
 * یک خط وصل میشه.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body>:
 *        <script src="tournament-panel.js"></script>
 *   3) همون جایی که وب‌ساکت رو می‌سازی:
 *        HokmTournament.attach(ws);
 *
 * درباره‌ی مدل تورنمنت (مهم):
 * چون در MVP فعلی دو بازیکنِ واقعیِ هر متچ همیشه هم‌تیمی هستن (نه رقیب
 * هم)، تورنمنت اینجا به‌شکل «لیگ امتیازی + حذفی» پیاده شده، نه برکت
 * ۱به۱ کلاسیک: عضو میشی، هر بازی معمولی‌ای که انجام میدی (quick match یا
 * اتاق خصوصی) امتیاز تورنمنتت رو زیاد می‌کنه، و در حالت «حذفی» بعد از هر
 * دور نصف پایین جدول حذف میشه تا یک نفر بمونه.
 */
(function () {
  "use strict";

  const CSS = `
  .hkt-fab {
    position: fixed; bottom: calc(74px + env(safe-area-inset-bottom)); inset-inline-start: calc(18px + env(safe-area-inset-left)); z-index: 9998;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #241016, #3a1420);
    border: 1px solid #d64d6e; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #ffd9e2; user-select: none;
    transition: transform .15s ease;
  }
  @media (hover:hover) and (pointer:fine){ .hkt-fab:hover { transform: translateY(-2px); } }
  @media (max-width:640px){
    .hkt-fab{
      bottom: calc(130px + env(safe-area-inset-bottom));
      inset-inline-start: calc(10px + env(safe-area-inset-left));
      padding:6px 10px; gap:6px; font-size:12px;
    }
  }

  .hkt-overlay {
    position: fixed; inset: 0; background: rgba(10,7,3,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hkt-overlay.hkt-open { display: flex; }
  .hkt-modal {
    width: min(92vw, 480px); max-height: 86vh; overflow: hidden;
    background: #1b0e12; border: 1px solid #d64d6e; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #ffd9e2; direction: rtl;
  }
  .hkt-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #3a1420; background: linear-gradient(135deg, #2a1017, #1b0e12); }
  .hkt-head h2 { margin: 0; font-size: 16px; }
  .hkt-close { cursor: pointer; font-size: 20px; line-height: 1; color: #e6b9c4; background: none; border: none; width:44px; height:44px; display:flex; align-items:center; justify-content:center; margin:-10px; }
  .hkt-tabs { display: flex; border-bottom: 1px solid #3a1420; }
  .hkt-tab { flex: 1; text-align: center; padding: 10px 4px; cursor: pointer; font-size: 13px; color: #a97785; border-bottom: 2px solid transparent; }
  .hkt-tab.hkt-active { color: #d64d6e; border-bottom-color: #d64d6e; }
  .hkt-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
  .hkt-panel { display: none; }
  .hkt-panel.hkt-active { display: block; }

  .hkt-card { background: #2a1017; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
  .hkt-card .hkt-name { font-weight: 700; font-size: 14px; }
  .hkt-card .hkt-meta { font-size: 12px; color: #a97785; margin-top: 2px; }
  .hkt-card button { margin-top: 8px; border: none; border-radius: 8px; background: #d64d6e; color: #1b0e12; font-weight: 700; padding: 7px 12px; cursor: pointer; }

  .hkt-field { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
  .hkt-field input, .hkt-field select { border-radius: 8px; border: 1px solid #3a1420; background: #12080b; color: #ffd9e2; padding: 8px; font-family: inherit; font-size: 16px; }
  .hkt-field button { border: none; border-radius: 8px; background: #d64d6e; color: #1b0e12; font-weight: 700; padding: 9px 12px; cursor: pointer; }

  .hkt-row { display: flex; align-items: center; justify-content: space-between; padding: 7px 4px; border-bottom: 1px solid #3a1420; font-size: 13px; }
  .hkt-row .hkt-rank { width: 22px; color: #a97785; }
  .hkt-row.hkt-me { background: rgba(214,77,110,.12); border-radius: 6px; }
  .hkt-out { text-decoration: line-through; color: #a97785; }
  .hkt-note { color: #a97785; font-size: 12px; text-align: center; padding: 20px 0; }

  .hkt-toast {
    position: fixed; bottom: 130px; inset-inline-start: 18px; z-index: 10000;
    background: #2a1017; border: 1px solid #d64d6e; color: #ffd9e2;
    padding: 10px 16px; border-radius: 10px; font-size: 13px;
    opacity: 0; transform: translateY(8px); transition: all .2s ease; pointer-events: none;
  }
  .hkt-toast.hkt-show { opacity: 1; transform: translateY(0); }
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

  class TournamentPanel {
    constructor() {
      this.ws = null;
      this.myPlayerId = null;
      this.openList = [];
      this.current = null;      // tournament_state payload
      this.leaderboard = [];
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => { this._send({ type: "list_tournaments" }); this._send({ type: "get_leaderboard" }); };
      if (ws.readyState === WebSocket.OPEN) request();
      ws.addEventListener("open", request);
      ws.addEventListener("message", (ev) => this._onMessage(ev));
    }

    _send(payload) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(payload));
    }

    _onMessage(ev) {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      switch (msg.type) {
        case "login_ok":
          this.myPlayerId = msg.player_id;
          break;
        case "tournament_list":
          this.openList = msg.tournaments || [];
          this._renderBrowse();
          break;
        case "tournament_state":
          this.current = msg.id ? msg : null;
          this._renderCurrent();
          this._renderBrowse();
          break;
        case "tournament_error":
          this._toast(msg.message);
          break;
        case "tournament_eliminated":
          this._toast(t('trn_eliminated','متأسفانه از تورنمنت حذف شدی — دفعه بعد بهتر میشه!'));
          break;
        case "tournament_finished":
          let prizeText = t('trn_prize_coins','+{coins} سکه').replace('{coins}', msg.prize.coins);
          if (msg.prize.gems) prizeText += t('trn_prize_gems','، +{gems} جم').replace('{gems}', msg.prize.gems);
          this._toast(t('trn_finished','تورنمنت تموم شد — مقام {place} 🏆 ({prize})').replace('{place}', msg.place).replace('{prize}', prizeText));
          this._send({ type: "list_tournaments" });
          break;
        case "leaderboard":
          this.leaderboard = msg.players || [];
          this._renderLeaderboard();
          break;
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hkt-fab", "🏆 " + t('trn_fab_label','تورنمنت'));
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hkt-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hkt-modal");
      modal.innerHTML = `
        <div class="hkt-head">
          <h2>🏆 ${t('trn_title','تورنمنت‌ها و لیدربورد')}</h2>
          <button class="hkt-close" type="button">×</button>
        </div>
        <div class="hkt-tabs">
          <button class="hkt-tab hkt-active" data-tab="current">${t('trn_tab_current','تورنمنت من')}</button>
          <button class="hkt-tab" data-tab="browse">${t('trn_tab_browse','لیست / ساخت')}</button>
          <button class="hkt-tab" data-tab="leaderboard">${t('trn_tab_leaderboard','لیدربورد جهانی')}</button>
        </div>
        <div class="hkt-body">
          <div class="hkt-panel hkt-active" data-panel="current"></div>
          <div class="hkt-panel" data-panel="browse"></div>
          <div class="hkt-panel" data-panel="leaderboard"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);
      this.modal = modal;

      modal.querySelector(".hkt-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hkt-tab").forEach((tab) => tab.addEventListener("click", () => this._switchTab(tab.dataset.tab)));

      this.toastEl = el("div", "hkt-toast");
      document.body.appendChild(this.toastEl);

      this._renderCurrent();
      this._renderBrowse();
      this._renderLeaderboard();
    }

    open() { this.overlay.classList.add("hkt-open"); }
    close() { this.overlay.classList.remove("hkt-open"); }

    _switchTab(name) {
      this.modal.querySelectorAll(".hkt-tab").forEach((t) => t.classList.toggle("hkt-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hkt-panel").forEach((p) => p.classList.toggle("hkt-active", p.dataset.panel === name));
    }

    _toast(text) {
      this.toastEl.textContent = text;
      this.toastEl.classList.add("hkt-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toastEl.classList.remove("hkt-show"), 3600);
    }

    _renderCurrent() {
      const panel = this.modal.querySelector('[data-panel="current"]');
      panel.innerHTML = "";
      if (!this.current) {
        panel.appendChild(el("div", "hkt-note", t('trn_none','توی هیچ تورنمنتی نیستی — از تب «لیست / ساخت» یکی بساز یا بهش بپیوند.')));
        return;
      }
      const cur = this.current;
      const card = el("div", "hkt-card");
      const statusMap = { registration: t('trn_status_registration','در حال ثبت‌نام'), active: t('trn_status_active','در حال برگزاری'), finished: t('trn_status_finished','تمام‌شده') };
      const statusFa = statusMap[cur.status] || cur.status;
      const modeFa = cur.mode === "knockout" ? t('trn_mode_knockout','حذفی') : t('trn_mode_league','لیگ');
      card.innerHTML = `
        <div class="hkt-name">${cur.name}</div>
        <div class="hkt-meta">${modeFa} · ${t('trn_capacity','ظرفیت')} ${cur.size} · ${statusFa}</div>
      `;
      panel.appendChild(card);

      if (cur.status === "registration" && cur.ownerId === this.myPlayerId) {
        const startBtn = el("button", null, t('trn_start_btn','شروع دستی تورنمنت'));
        startBtn.addEventListener("click", () => this._send({ type: "start_tournament", tournamentId: cur.id }));
        panel.appendChild(startBtn);
      }
      if (cur.status === "registration") {
        const leaveBtn = el("button", null, t('trn_withdraw_btn','انصراف از ثبت‌نام'));
        leaveBtn.style.background = "#6b3a44";
        leaveBtn.addEventListener("click", () => this._send({ type: "leave_tournament" }));
        panel.appendChild(leaveBtn);
      }

      (cur.standings || []).forEach((s, i) => {
        const row = el("div", "hkt-row" + (s.playerId === this.myPlayerId ? " hkt-me" : ""));
        const nameHtml = s.eliminated ? `<span class="hkt-out">${s.name}</span>` : s.name;
        row.innerHTML = `<span><span class="hkt-rank">${i + 1}.</span>${nameHtml}</span><span>${t('trn_points_wl','{points} امتیاز ({w}ب/{l}ش)').replace('{points}', s.points).replace('{w}', s.wins).replace('{l}', s.losses)}</span>`;
        panel.appendChild(row);
      });
    }

    _renderBrowse() {
      const panel = this.modal.querySelector('[data-panel="browse"]');
      panel.innerHTML = "";

      const field = el("div", "hkt-field");
      field.innerHTML = `
        <input type="text" placeholder="${t('trn_new_name_placeholder','نام تورنمنت جدید')}" data-name />
        <select data-size>
          <option value="4">${t('trn_size_4','۴ نفره')}</option>
          <option value="8">${t('trn_size_8','۸ نفره')}</option>
          <option value="16">${t('trn_size_16','۱۶ نفره')}</option>
          <option value="32">${t('trn_size_32','۳۲ نفره')}</option>
        </select>
        <select data-mode>
          <option value="league">${t('trn_mode_league_option','لیگ (امتیازی)')}</option>
          <option value="knockout">${t('trn_mode_knockout','حذفی')}</option>
        </select>
      `;
      const createBtn = el("button", null, t('trn_create_btn','ساخت تورنمنت'));
      createBtn.addEventListener("click", () => {
        const name = field.querySelector("[data-name]").value.trim();
        const size = parseInt(field.querySelector("[data-size]").value, 10);
        const mode = field.querySelector("[data-mode]").value;
        if (name) this._send({ type: "create_tournament", name, size, mode });
      });
      field.appendChild(createBtn);
      panel.appendChild(field);

      if (!this.openList.length) {
        panel.appendChild(el("div", "hkt-note", t('trn_no_open','الان تورنمنت بازی برای ثبت‌نام نیست — یکی بساز!')));
        return;
      }
      this.openList.forEach((item) => {
        const card = el("div", "hkt-card");
        const modeFa = item.mode === "knockout" ? t('trn_mode_knockout','حذفی') : t('trn_mode_league','لیگ');
        card.innerHTML = `<div class="hkt-name">${item.name}</div><div class="hkt-meta">${modeFa} · ${item.joined}/${item.size} ${t('trn_people_suffix','نفر')}</div>`;
        const joinBtn = el("button", null, t('trn_join_btn','پیوستن'));
        joinBtn.addEventListener("click", () => this._send({ type: "join_tournament", tournamentId: item.id }));
        card.appendChild(joinBtn);
        panel.appendChild(card);
      });
    }

    _renderLeaderboard() {
      const panel = this.modal.querySelector('[data-panel="leaderboard"]');
      panel.innerHTML = "";
      if (!this.leaderboard.length) {
        panel.appendChild(el("div", "hkt-note", t('trn_no_ranked','هنوز کسی رتبه‌بندی نشده.')));
        return;
      }
      this.leaderboard.forEach((pl, i) => {
        const row = el("div", "hkt-row" + (pl.playerId === this.myPlayerId ? " hkt-me" : ""));
        row.innerHTML = `<span><span class="hkt-rank">${i + 1}.</span>${pl.rank.icon || ""} ${pl.name}</span><span>${pl.rr} RR</span>`;
        panel.appendChild(row);
      });
    }
  }

  const instance = new TournamentPanel();
  window.HokmTournament = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
