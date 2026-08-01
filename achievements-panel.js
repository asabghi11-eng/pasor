/*!
 * achievements-panel.js — Phase 13 UI for Hokm (دستاوردها / Achievements).
 *
 * درباره این فایل:
 * سرور (server.py) و ماژول hokm_achievements.py از قبل کاملاً آماده‌ن
 * (get_achievements / achievements_state / claim_achievement /
 * claim_achievement_result) ولی هیچ رابط کاربری‌ای براشون وجود نداشت.
 * درست مثل economy-panel.js و بقیه‌ی پنل‌ها، این فایل کاملاً مستقله
 * (self-contained) تا بدون دست‌زدن به hokm-phase4-online.html فقط
 * وصلش کنی.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) این خط رو قبل از بسته‌شدن </body> اضافه کن (بعد از
 *      economy-panel.js اگه اونم نصبه، فرقی نداره ترتیب):
 *        <script src="achievements-panel.js"></script>
 *   3) دقیقاً همون‌جایی که وب‌ساکت رو می‌سازی، یک خط زیرش اضافه کن:
 *        HokmAchievements.attach(ws);
 *      همین. مثل بقیه‌ی پنل‌ها با addEventListener روی همون ws گوش
 *      میده و به رفتار فعلی بازی دست نمی‌زنه.
 *
 * چیزی که خودش انجام می‌ده:
 *   - بعد از باز شدن اتصال، خودکار "get_achievements" می‌فرسته.
 *   - یک دکمه شناور (🏆) با نشان تعداد دستاوردهای «باز شده ولی دریافت
 *     نشده» گوشه صفحه نشون می‌ده.
 *   - با کلیک، پنلی باز میشه که همه‌ی دستاوردها رو دسته‌بندی‌شده،
 *     با نوار پیشرفت و دکمه‌ی دریافت جایزه (وقتی باز شده باشن) نشون
 *     می‌ده.
 */
(function () {
  "use strict";

  const CSS = `
  .hka-fab {
    position: fixed; bottom: calc(228px + env(safe-area-inset-bottom)); inset-inline-end: calc(18px + env(safe-area-inset-right)); z-index: 9998;
    display: flex; align-items: center; justify-content: center;
    width: 46px; height: 46px;
    background: linear-gradient(135deg, #241a0f, #3a2712);
    border: 1px solid #caa14d; border-radius: 999px;
    cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-size: 20px; user-select: none; transition: transform .15s ease;
  }
  @media (hover:hover) and (pointer:fine){ .hka-fab:hover { transform: translateY(-2px); } }
  @media (max-width:640px){
    .hka-fab{
      bottom: calc(298px + env(safe-area-inset-bottom));
      inset-inline-end: calc(10px + env(safe-area-inset-right));
      width:40px; height:40px; font-size:17px;
    }
  }
  .hka-badge {
    position: absolute; top: -4px; inset-inline-end: -4px;
    background: #d94f4f; color: #fff; font-size: 11px; font-weight: 700;
    border-radius: 999px; min-width: 18px; height: 18px; padding: 0 4px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 0 2px #1b140b;
  }
  .hka-badge.hka-hidden { display: none; }

  .hka-overlay {
    position: fixed; inset: 0; background: rgba(10,7,3,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hka-overlay.hka-open { display: flex; }
  .hka-modal {
    width: min(92vw, 520px); max-height: 86vh; overflow: hidden;
    background: #1b140b; border: 1px solid #caa14d; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #f3e3c0; direction: rtl;
  }
  .hka-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px; border-bottom: 1px solid #3a2712;
    background: linear-gradient(135deg, #2a1d10, #1b140b);
  }
  .hka-head h2 { margin: 0; font-size: 16px; }
  .hka-close { cursor: pointer; font-size: 20px; line-height: 1; color: #d8c39a; background: none; border: none; width:44px; height:44px; display:flex; align-items:center; justify-content:center; margin:-10px; }
  .hka-sub { padding: 8px 16px; font-size: 12px; color: #b7a071; border-bottom: 1px solid #3a2712; }
  .hka-body { overflow-y: auto; padding: 10px 12px 16px; display: flex; flex-direction: column; gap: 8px; }

  .hka-cat-title {
    font-size: 12px; color: #caa14d; font-weight: 700; margin: 10px 4px 2px;
  }
  .hka-card {
    display: flex; align-items: center; gap: 10px; padding: 10px;
    background: #241a0f; border: 1px solid #3a2712; border-radius: 12px;
  }
  .hka-card.hka-done { opacity: .55; }
  .hka-card.hka-ready { border-color: #ffd76a; box-shadow: 0 0 0 1px #ffd76a inset; }
  .hka-icon { font-size: 24px; width: 32px; text-align: center; flex-shrink: 0; }
  .hka-info { flex: 1; min-width: 0; }
  .hka-name { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
  .hka-bar-wrap { height: 6px; border-radius: 999px; background: #3a2712; overflow: hidden; }
  .hka-bar { height: 100%; background: linear-gradient(90deg,#caa14d,#ffd76a); }
  .hka-progtext { font-size: 10px; color: #b7a071; margin-top: 3px; }
  .hka-reward { font-size: 10px; color: #ffd76a; margin-top: 3px; }
  .hka-claim {
    flex-shrink: 0; background: linear-gradient(135deg,#caa14d,#e8b95c); color: #241a0f;
    border: none; border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 700;
    cursor: pointer;
  }
  .hka-claim:disabled { opacity: .4; cursor: default; }

  .hka-toast {
    position: fixed; bottom: 76px; inset-inline-end: 18px; z-index: 10000;
    background: #241a0f; border: 1px solid #ffd76a; color: #ffd76a;
    padding: 10px 14px; border-radius: 10px; font-size: 13px;
    box-shadow: 0 6px 20px rgba(0,0,0,.4); direction: rtl;
    opacity: 0; transform: translateY(6px); transition: all .2s ease;
    pointer-events: none;
  }
  .hka-toast.hka-show { opacity: 1; transform: translateY(0); }
  `;

  const CATEGORY_LABEL_FA = {
    wins: "بردها", tricks: "خشت‌ها", sur: "سور", hakem: "حاکم",
    streak: "برد پیاپی", level: "لول", rank: "رتبه", social: "اجتماعی",
    worldcup: "جام جهانی", collector: "کلکسیون",
  };
  function categoryLabel(cat) {
    return t('ach_cat_' + cat, CATEGORY_LABEL_FA[cat] || cat);
  }

  function injectStyle() {
    if (document.getElementById("hka-style")) return;
    const s = document.createElement("style");
    s.id = "hka-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  class AchievementsPanel {
    constructor() {
      this.ws = null;
      this.achievements = [];
      this.unclaimedCount = 0;
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => this._send({ type: "get_achievements" });
      if (ws.readyState === WebSocket.OPEN) request();
      ws.addEventListener("open", request);
      ws.addEventListener("message", (ev) => this._onMessage(ev));
    }

    _send(payload) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(payload));
      }
    }

    _onMessage(ev) {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }

      if (msg.type === "achievements_state") {
        this.achievements = msg.achievements || [];
        this.unclaimedCount = msg.unclaimedCount || 0;
        this._renderAll();
      } else if (msg.type === "claim_achievement_result") {
        if (msg.ok) {
          const r = msg.reward || {};
          let text = t('ach_claimed','دستاورد دریافت شد: {coins} سکه').replace('{coins}', r.coins || 0);
          if (r.xp) text += t('ach_xp_suffix','، {xp} XP').replace('{xp}', r.xp);
          if (r.gems) text += t('ach_gems_suffix','، {gems} جم').replace('{gems}', r.gems);
          this._toast(text);
        } else {
          this._toast(msg.error || t('ach_claim_error','خطا در دریافت دستاورد'));
        }
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hka-fab", `🏆<span class="hka-badge hka-hidden" data-badge>0</span>`);
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hka-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hka-modal");
      modal.innerHTML = `
        <div class="hka-head">
          <h2>🏆 ${t('ach_title','دستاوردها')}</h2>
          <button class="hka-close" type="button">×</button>
        </div>
        <div class="hka-sub" data-summary></div>
        <div class="hka-body" data-list></div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);

      modal.querySelector(".hka-close").addEventListener("click", () => this.close());

      this.toast = el("div", "hka-toast");
      document.body.appendChild(this.toast);
    }

    open() { this.overlay.classList.add("hka-open"); this._send({ type: "get_achievements" }); }
    close() { this.overlay.classList.remove("hka-open"); }

    _toast(text) {
      this.toast.textContent = text;
      this.toast.classList.add("hka-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toast.classList.remove("hka-show"), 3200);
    }

    _renderAll() {
      const badge = this.fab.querySelector("[data-badge]");
      badge.textContent = this.unclaimedCount;
      badge.classList.toggle("hka-hidden", this.unclaimedCount <= 0);

      const done = this.achievements.filter((a) => a.claimed).length;
      const summary = this.overlay.querySelector("[data-summary]");
      summary.textContent = t('ach_summary','{done} از {total} دریافت شده').replace('{done}', done).replace('{total}', this.achievements.length);

      const list = this.overlay.querySelector("[data-list]");
      list.innerHTML = "";

      const byCategory = {};
      this.achievements.forEach((a) => {
        (byCategory[a.category] = byCategory[a.category] || []).push(a);
      });

      Object.keys(byCategory).forEach((cat) => {
        list.appendChild(el("div", "hka-cat-title", categoryLabel(cat)));
        byCategory[cat].forEach((a) => list.appendChild(this._card(a)));
      });
    }

    _card(a) {
      const ready = a.unlocked && !a.claimed;
      const card = el("div", "hka-card" + (a.claimed ? " hka-done" : "") + (ready ? " hka-ready" : ""));
      const pct = a.target > 0 ? Math.round((100 * a.progress) / a.target) : 100;

      const rewardBits = [];
      if (a.reward) {
        if (a.reward.coins) rewardBits.push(`🪙${a.reward.coins}`);
        if (a.reward.xp) rewardBits.push(`XP ${a.reward.xp}`);
        if (a.reward.gems) rewardBits.push(`💎${a.reward.gems}`);
      }

      card.innerHTML = `
        <div class="hka-icon">${a.icon || "🏅"}</div>
        <div class="hka-info">
          <div class="hka-name">${t('ach_name_' + a.id, a.nameFa)}</div>
          <div class="hka-bar-wrap"><div class="hka-bar" style="width:${pct}%"></div></div>
          <div class="hka-progtext">${a.progress} / ${a.target}</div>
          ${rewardBits.length ? `<div class="hka-reward">${rewardBits.join(" · ")}</div>` : ""}
        </div>
      `;

      const btn = el("button", "hka-claim", a.claimed ? t('ach_claimed_btn','دریافت شد') : (ready ? t('ach_claim_btn','دریافت جایزه') : t('ach_locked','قفل')));
      btn.disabled = !ready;
      btn.addEventListener("click", () => this._send({ type: "claim_achievement", achievementId: a.id }));
      card.appendChild(btn);

      return card;
    }
  }

  const instance = new AchievementsPanel();
  window.HokmAchievements = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
