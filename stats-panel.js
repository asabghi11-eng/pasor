/*!
 * stats-panel.js — Phase 11 UI for Hokm (آمار، تاریخچه/ریپلی مسابقات،
 * تحلیل هوشمند بعد از هر بازی، لیدربورد جهانی بر اساس آمار، و پیشنهاد حرکت).
 *
 * همون الگوی economy-panel.js / social-panel.js / tournament-panel.js:
 * کاملاً مستقل، فقط با یک خط وصل میشه.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body>:
 *        <script src="stats-panel.js"></script>
 *   3) همون جایی که وب‌ساکت رو می‌سازی:
 *        HokmStats.attach(ws);
 *
 * درباره‌ی "تحلیل هوشمند" (مهم، برای شفافیت):
 * این یک مربی ابتکاری/heuristic هست، نه یک مدل واقعی. سرور هر حرکت رو با
 * حرکتی که هوش مصنوعیِ بات‌ها انتخاب می‌کرد مقایسه می‌کنه و یه برچسب کوتاه
 * بهش میده (مثلاً «حکم غیرضروری» یا «واگذاری دست»)، بعد در پایان مسابقه
 * چند تا نکته‌ی کوتاه بر اساس پرتکرارترین برچسب‌ها می‌سازه. یک تحلیل‌گر
 * واقعاً بهینه باید کل برگ‌های باقی‌مونده رو جستجو کنه که فعلاً خارج از
 * محدوده‌ی این نسخه‌ست.
 */
(function () {
  "use strict";

  const SUIT_SYMBOL = { S: "♠", H: "♥", D: "♦", C: "♣" };
  const SUIT_COLOR = { S: "black", H: "red", D: "red", C: "black" };
  function seatLabel(seat) {
    if (seat === "south") return t('stt_you','شما');
    const NAMES = { north: "سارا", west: "امیر", east: "رضا" };
    return NAMES[seat] || seat;
  }
  const RANK_LABEL = { 11: "J", 12: "Q", 13: "K", 14: "A" };
  function rankLabel(r) { return RANK_LABEL[r] || String(r); }
  function cardLabel(c) {
    if (!c) return "";
    return `<span style="color:${SUIT_COLOR[c.suit] === "red" ? "#e5556b" : "#ffd9e2"}">${SUIT_SYMBOL[c.suit] || c.suit}${rankLabel(c.rank)}</span>`;
  }

  const CSS = `
  .hkst-fab {
    position: fixed; bottom: calc(124px + env(safe-area-inset-bottom)); inset-inline-end: calc(18px + env(safe-area-inset-right)); z-index: 9998;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #10202a, #143140);
    border: 1px solid #3fb6d6; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #d7f3ff; user-select: none;
    transition: transform .15s ease;
  }
  @media (hover:hover) and (pointer:fine){ .hkst-fab:hover { transform: translateY(-2px); } }
  @media (max-width:640px){
    .hkst-fab{
      bottom: calc(214px + env(safe-area-inset-bottom));
      inset-inline-end: calc(10px + env(safe-area-inset-right));
      padding:6px 10px; gap:6px; font-size:12px;
    }
  }

  .hkst-overlay {
    position: fixed; inset: 0; background: rgba(6,10,12,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hkst-overlay.hkst-open { display: flex; }
  .hkst-modal {
    width: min(92vw, 480px); max-height: 86vh; overflow: hidden;
    background: #0d1a20; border: 1px solid #3fb6d6; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #d7f3ff; direction: rtl;
  }
  .hkst-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #17323d; background: linear-gradient(135deg, #12242c, #0d1a20); }
  .hkst-head h2 { margin: 0; font-size: 16px; }
  .hkst-close { cursor: pointer; font-size: 20px; line-height: 1; color: #a9d8e8; background: none; border: none; width:44px; height:44px; display:flex; align-items:center; justify-content:center; margin:-10px; }
  .hkst-tabs { display: flex; border-bottom: 1px solid #17323d; }
  .hkst-tab { flex: 1; text-align: center; padding: 10px 4px; cursor: pointer; font-size: 13px; color: #7aa6b5; border-bottom: 2px solid transparent; }
  .hkst-tab.hkst-active { color: #3fb6d6; border-bottom-color: #3fb6d6; }
  .hkst-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
  .hkst-panel { display: none; }
  .hkst-panel.hkst-active { display: block; }

  .hkst-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
  .hkst-stat { background: #12242c; border-radius: 10px; padding: 10px; text-align: center; }
  .hkst-stat .hkst-num { font-size: 18px; font-weight: 700; color: #3fb6d6; }
  .hkst-stat .hkst-lbl { font-size: 11px; color: #7aa6b5; margin-top: 2px; }

  .hkst-hint-btn { width: 100%; border: none; border-radius: 8px; background: #3fb6d6; color: #0d1a20; font-weight: 700; padding: 10px 12px; cursor: pointer; margin-bottom: 4px; }
  .hkst-hint-btn:disabled { background: #1c3a44; color: #5c8492; cursor: not-allowed; }

  .hkst-card { background: #12242c; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
  .hkst-card .hkst-name { font-weight: 700; font-size: 14px; display: flex; justify-content: space-between; }
  .hkst-card .hkst-meta { font-size: 12px; color: #7aa6b5; margin-top: 2px; }
  .hkst-card button { margin-top: 8px; border: none; border-radius: 8px; background: #3fb6d6; color: #0d1a20; font-weight: 700; padding: 7px 12px; cursor: pointer; }
  .hkst-badge { border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
  .hkst-badge.hkst-win { background: rgba(63,214,138,.18); color: #3fd68a; }
  .hkst-badge.hkst-loss { background: rgba(230,90,90,.18); color: #e65a5a; }

  .hkst-row { display: flex; align-items: center; justify-content: space-between; padding: 7px 4px; border-bottom: 1px solid #17323d; font-size: 13px; }
  .hkst-row .hkst-rank { width: 22px; color: #7aa6b5; }
  .hkst-row.hkst-me { background: rgba(63,182,214,.12); border-radius: 6px; }
  .hkst-note { color: #7aa6b5; font-size: 12px; text-align: center; padding: 20px 0; }

  .hkst-tips { margin: 10px 0 0; padding-inline-start: 18px; font-size: 12px; color: #a9d8e8; }
  .hkst-tips li { margin-bottom: 4px; }

  .hkst-hand { background: #10202a; border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; }
  .hkst-hand .hkst-hand-head { font-size: 12px; color: #7aa6b5; margin-bottom: 4px; }
  .hkst-trick { font-size: 13px; padding: 2px 0; display: flex; justify-content: space-between; }
  .hkst-back { background: none; border: none; color: #3fb6d6; cursor: pointer; font-size: 13px; padding: 0 0 10px; }

  .hkst-toast {
    position: fixed; bottom: 180px; inset-inline-end: 18px; z-index: 10000;
    background: #12242c; border: 1px solid #3fb6d6; color: #d7f3ff;
    padding: 10px 16px; border-radius: 10px; font-size: 13px; max-width: 280px;
    opacity: 0; transform: translateY(8px); transition: all .2s ease; pointer-events: none;
  }
  .hkst-toast.hkst-show { opacity: 1; transform: translateY(0); }
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

  function fmtDate(ts) {
    try { return new Date(ts * 1000).toLocaleDateString("fa-IR"); } catch (e) { return ""; }
  }

  class StatsPanel {
    constructor() {
      this.ws = null;
      this.myPlayerId = null;
      this.stats = null;
      this.rank = null;
      this.matches = [];
      this.leaderboard = { top: [], me: null };
      this.replayView = null;    // {matchId, match} while viewing a replay
      this.myTurn = false;       // true when it's my turn to play a card
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => {
        this._send({ type: "get_stats" });
        this._send({ type: "get_match_history" });
        this._send({ type: "get_stats_leaderboard" });
      };
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
        case "stats_state":
          this.stats = msg.stats;
          this.rank = msg.rank;
          this._renderStats();
          break;
        case "match_history":
          this.matches = msg.matches || [];
          this._renderHistory();
          break;
        case "match_recorded":
          // A match I was in just ended — refresh everything live.
          this.stats = msg.stats;
          this._renderStats();
          this._send({ type: "get_match_history" });
          this._send({ type: "get_stats_leaderboard" });
          if (msg.analysis && msg.analysis.tips && msg.analysis.tips.length) {
            this._toast("🧠 " + msg.analysis.tips[0]);
          }
          break;
        case "replay":
          this.replayView = msg.match || null;
          this._renderHistory();
          break;
        case "stats_leaderboard":
          this.leaderboard = { top: msg.top || [], me: msg.me || null };
          this._renderLeaderboard();
          break;
        case "suggestion":
          if (msg.card) {
            this._toast(t('stt_suggestion','💡 پیشنهاد: {card} — {reason}').replace('{card}', (SUIT_SYMBOL[msg.card.suit] || msg.card.suit) + rankLabel(msg.card.rank)).replace('{reason}', msg.reason || ''));
          } else {
            this._toast(t('stt_suggestion_needs_turn','الان نوبت توئه که این پیشنهاد معنی داشته باشه.'));
          }
          break;
        case "game_state":
          this.myTurn = !!(msg.mySeat === "south" || msg.mySeat === "north")
            && msg.phase === "playing" && msg.turn === msg.mySeat;
          this._updateHintButton();
          break;
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hkst-fab", "📊 " + t('stt_fab_label','آمار'));
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hkst-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hkst-modal");
      modal.innerHTML = `
        <div class="hkst-head">
          <h2>📊 ${t('stt_title','آمار، تاریخچه و لیدربورد')}</h2>
          <button class="hkst-close" type="button">×</button>
        </div>
        <div class="hkst-tabs">
          <button class="hkst-tab hkst-active" data-tab="stats">${t('stt_tab_stats','آمار من')}</button>
          <button class="hkst-tab" data-tab="history">${t('stt_tab_history','تاریخچه / ریپلی')}</button>
          <button class="hkst-tab" data-tab="leaderboard">${t('stt_tab_leaderboard','لیدربورد')}</button>
        </div>
        <div class="hkst-body">
          <div class="hkst-panel hkst-active" data-panel="stats"></div>
          <div class="hkst-panel" data-panel="history"></div>
          <div class="hkst-panel" data-panel="leaderboard"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);
      this.modal = modal;

      modal.querySelector(".hkst-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hkst-tab").forEach((tab) => tab.addEventListener("click", () => this._switchTab(tab.dataset.tab)));

      this.toastEl = el("div", "hkst-toast");
      document.body.appendChild(this.toastEl);

      this._renderStats();
      this._renderHistory();
      this._renderLeaderboard();
    }

    open() { this.overlay.classList.add("hkst-open"); }
    close() { this.overlay.classList.remove("hkst-open"); }

    _switchTab(name) {
      this.modal.querySelectorAll(".hkst-tab").forEach((t) => t.classList.toggle("hkst-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hkst-panel").forEach((p) => p.classList.toggle("hkst-active", p.dataset.panel === name));
    }

    _toast(text) {
      this.toastEl.textContent = text;
      this.toastEl.classList.add("hkst-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toastEl.classList.remove("hkst-show"), 4200);
    }

    _updateHintButton() {
      if (this._hintBtn) this._hintBtn.disabled = !this.myTurn;
    }

    _renderStats() {
      const panel = this.modal.querySelector('[data-panel="stats"]');
      panel.innerHTML = "";

      this._hintBtn = el("button", "hkst-hint-btn", "💡 " + t('stt_hint_btn','پیشنهاد حرکت (فقط سر نوبت خودت)'));
      this._hintBtn.disabled = !this.myTurn;
      this._hintBtn.addEventListener("click", () => this._send({ type: "suggest_move" }));
      panel.appendChild(this._hintBtn);

      if (!this.stats) {
        panel.appendChild(el("div", "hkst-note", t('stt_no_stats','هنوز آماری ثبت نشده — یک مسابقه بازی کن!')));
        return;
      }
      const s = this.stats;
      const grid = el("div", "hkst-grid");
      const items = [
        [s.matchesPlayed ?? 0, t('stt_stat_matches','مسابقات')],
        [s.matchesWon ?? 0, t('stt_stat_wins','بردها')],
        [(s.winRate ?? 0) + "%", t('stt_stat_winrate','درصد برد')],
        [s.tricksWon ?? 0, t('stt_stat_tricks','برگ‌های برده')],
        [s.surWon ?? 0, t('stt_stat_sur','سور')],
        [(s.hakemWinRate ?? 0) + "%", t('stt_stat_hakem_winrate','درصد برد به‌عنوان حاکم')],
        [s.bestWinStreak ?? 0, t('stt_stat_best_streak','بهترین رکورد برد پیاپی')],
        [(s.surRate ?? 0) + "%", t('stt_stat_sur_rate','درصد سور از دست‌های برده')],
      ];
      items.forEach(([num, lbl]) => {
        const box = el("div", "hkst-stat");
        box.innerHTML = `<div class="hkst-num">${num}</div><div class="hkst-lbl">${lbl}</div>`;
        grid.appendChild(box);
      });
      panel.appendChild(grid);
    }

    _renderHistory() {
      const panel = this.modal.querySelector('[data-panel="history"]');
      panel.innerHTML = "";

      if (this.replayView) {
        this._renderReplay(panel);
        return;
      }

      if (!this.matches.length) {
        panel.appendChild(el("div", "hkst-note", t('stt_no_matches','هنوز مسابقه‌ای تموم نشده.')));
        return;
      }
      this.matches.forEach((m) => {
        const card = el("div", "hkst-card");
        const badge = m.won ? `<span class="hkst-badge hkst-win">${t('stt_win_badge','برد')}</span>` : `<span class="hkst-badge hkst-loss">${t('stt_loss_badge','باخت')}</span>`;
        card.innerHTML = `
          <div class="hkst-name">${fmtDate(m.ts)} ${badge}</div>
          <div class="hkst-meta">${t('stt_hands_score','امتیاز دست‌ها:')} ${m.roundsWon.A} - ${m.roundsWon.B}${m.analysis ? ` · ${t('stt_optimal_rate','بهینه:')} ${m.analysis.optimalRate}%` : ""}</div>
        `;
        const btn = el("button", null, t('stt_view_replay','دیدن ریپلی'));
        btn.addEventListener("click", () => this._send({ type: "get_replay", matchId: m.matchId }));
        card.appendChild(btn);
        panel.appendChild(card);
      });
    }

    _renderReplay(panel) {
      const back = el("button", "hkst-back", "← " + t('stt_back_to_history','بازگشت به تاریخچه'));
      back.addEventListener("click", () => { this.replayView = null; this._renderHistory(); });
      panel.appendChild(back);

      const match = this.replayView;
      if (!match) {
        panel.appendChild(el("div", "hkst-note", t('stt_replay_not_found','این ریپلی پیدا نشد.')));
        return;
      }

      if (match.analysis && match.analysis.tips && match.analysis.tips.length) {
        const tipsBox = el("div", "hkst-card");
        tipsBox.innerHTML = `<div class="hkst-name">🧠 ${t('stt_smart_analysis','تحلیل هوشمند (بهینه: {rate}%)').replace('{rate}', match.analysis.optimalRate)}</div>`;
        const ul = el("ul", "hkst-tips");
        match.analysis.tips.forEach((t) => ul.appendChild(el("li", null, t)));
        tipsBox.appendChild(ul);
        panel.appendChild(tipsBox);
      }

      (match.hands || []).forEach((h) => {
        const box = el("div", "hkst-hand");
        box.innerHTML = `<div class="hkst-hand-head">${t('stt_hand_label','دست')} ${h.handNumber} — ${t('stt_hakem_label','حاکم:')} ${seatLabel(h.hakem)} — ${t('stt_trump_label','حکم:')} ${SUIT_SYMBOL[h.trump] || h.trump} — ${t('stt_result_label','نتیجه:')} ${h.tricksWon.A}-${h.tricksWon.B}</div>`;
        (h.tricks || []).forEach((trick, i) => {
          const row = el("div", "hkst-trick");
          const cardsStr = trick.trick.map((play) => `${seatLabel(play.seat)}:${cardLabel(play.card)}`).join("  ");
          row.innerHTML = `<span>${i + 1}) ${cardsStr}</span><span>🏆 ${seatLabel(trick.winnerSeat)}</span>`;
          box.appendChild(row);
        });
        panel.appendChild(box);
      });
    }

    _renderLeaderboard() {
      const panel = this.modal.querySelector('[data-panel="leaderboard"]');
      panel.innerHTML = "";
      const top = this.leaderboard.top || [];
      if (!top.length) {
        panel.appendChild(el("div", "hkst-note", t('stt_no_ranked','هنوز کسی مسابقه‌ای تموم نکرده.')));
        return;
      }
      top.forEach((pl) => {
        const row = el("div", "hkst-row" + (pl.playerId === this.myPlayerId ? " hkst-me" : ""));
        row.innerHTML = `<span><span class="hkst-rank">${pl.position}.</span>${pl.name}</span><span>${t('stt_wins_pct','{wins} برد ({rate}%)').replace('{wins}', pl.matchesWon).replace('{rate}', pl.winRate)}</span>`;
        panel.appendChild(row);
      });
      const me = this.leaderboard.me;
      if (me && me.position > top.length) {
        const sep = el("div", "hkst-note", "···");
        panel.appendChild(sep);
        const row = el("div", "hkst-row hkst-me");
        row.innerHTML = `<span><span class="hkst-rank">${me.position}.</span>${me.name}</span><span>${t('stt_wins_pct','{wins} برد ({rate}%)').replace('{wins}', me.matchesWon).replace('{rate}', me.winRate)}</span>`;
        panel.appendChild(row);
      }
    }
  }

  const instance = new StatsPanel();
  window.HokmStats = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
