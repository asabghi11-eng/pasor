/*!
 * economy-panel.js — Phase 6 UI for Hokm (سکه/جم/XP، ماموریت روزانه، فروشگاه،
 * گردونه شانس، جعبه جایزه).
 *
 * درباره این فایل:
 * چون hokm-phase4-online.html خیلی بزرگه و من نمی‌تونم محتوای دقیقش رو از
 * این‌جا بخونم، این پنل رو کاملاً مستقل (self-contained) نوشتم تا بدون
 * ریسکِ خراب کردن چیزی که از قبل کار می‌کنه، فقط وصلش کنی.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) این خط رو قبل از بسته‌شدن </body> اضافه کن:
 *        <script src="economy-panel.js"></script>
 *   3) دقیقاً همون جایی که وب‌ساکت رو می‌سازی (چیزی شبیه
 *      `const ws = new WebSocket("ws://localhost:8000/ws")`) یک خط زیرش
 *      اضافه کن:
 *        HokmEconomy.attach(ws);
 *      همین. لازم نیست به هندلر onmessage یا onopen خودت دست بزنی —
 *      این پنل با addEventListener روی همون ws گوش میده، بدون این‌که
 *      رفتار فعلی بازی رو تغییر بده.
 *
 * چیزی که خودش انجام می‌ده:
 *   - بعد از باز شدن اتصال، خودکار "get_economy" می‌فرسته و کیف پول رو
 *     می‌گیره.
 *   - یک دکمه شناور (سکه/جم/لول) گوشه صفحه نشون می‌ده که با کلیک روش
 *     پنل کامل (ماموریت‌ها/فروشگاه/گردونه/جعبه) باز میشه.
 *   - به پیام‌های economy_state / economy_update / claim_mission_result /
 *     spin_wheel_result / buy_item_result / open_box_result که سرور
 *     (server.py فاز ۶) می‌فرسته گوش می‌ده و UI رو آپدیت می‌کنه.
 */
(function () {
  "use strict";

  const CSS = `
  .hke-fab {
    position: fixed; bottom: 18px; inset-inline-end: 18px; z-index: 9998;
    display: flex; align-items: center; gap: 10px;
    background: linear-gradient(135deg, #241a0f, #3a2712);
    border: 1px solid #caa14d; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #f3e3c0; user-select: none;
    transition: transform .15s ease;
  }
  .hke-fab:hover { transform: translateY(-2px); }
  .hke-fab .hke-lvl {
    background: #caa14d; color: #241a0f; font-weight: 700; font-size: 12px;
    border-radius: 999px; padding: 2px 8px;
  }
  .hke-fab .hke-chip { display: flex; align-items: center; gap: 4px; font-size: 14px; font-weight: 600; }

  .hke-overlay {
    position: fixed; inset: 0; background: rgba(10,7,3,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hke-overlay.hke-open { display: flex; }
  .hke-modal {
    width: min(92vw, 480px); max-height: 86vh; overflow: hidden;
    background: #1b140b; border: 1px solid #caa14d; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #f3e3c0; direction: rtl;
  }
  .hke-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px; border-bottom: 1px solid #3a2712;
    background: linear-gradient(135deg, #2a1d10, #1b140b);
  }
  .hke-head h2 { margin: 0; font-size: 16px; }
  .hke-close { cursor: pointer; font-size: 20px; line-height: 1; color: #d8c39a; background: none; border: none; }
  .hke-wallet-row { display: flex; gap: 14px; padding: 12px 16px; font-size: 14px; }
  .hke-wallet-row b { color: #ffd76a; }
  .hke-xpbar-wrap { padding: 0 16px 12px; }
  .hke-xpbar { height: 8px; border-radius: 999px; background: #3a2712; overflow: hidden; }
  .hke-xpbar > div { height: 100%; background: linear-gradient(90deg,#caa14d,#ffd76a); }
  .hke-xptext { font-size: 11px; color: #b7a071; margin-top: 4px; }

  .hke-tabs { display: flex; border-bottom: 1px solid #3a2712; }
  .hke-tab {
    flex: 1; text-align: center; padding: 10px 4px; cursor: pointer;
    font-size: 13px; color: #b7a071; background: none; border: none; border-bottom: 2px solid transparent;
  }
  .hke-tab.hke-active { color: #ffd76a; border-color: #ffd76a; }
  .hke-body { padding: 14px 16px; overflow-y: auto; flex: 1; }
  .hke-panel { display: none; }
  .hke-panel.hke-active { display: block; }

  .hke-mission {
    background: #241a0f; border: 1px solid #3a2712; border-radius: 12px;
    padding: 10px 12px; margin-bottom: 10px;
  }
  .hke-mission-top { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
  .hke-mission-bar { height: 6px; border-radius: 999px; background: #3a2712; overflow: hidden; margin-bottom: 6px; }
  .hke-mission-bar > div { height: 100%; background: #6bc17a; }
  .hke-mission-bottom { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #b7a071; }
  .hke-btn {
    background: linear-gradient(135deg,#caa14d,#a97f2f); color: #1b140b; border: none;
    border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer;
  }
  .hke-btn:disabled { opacity: .4; cursor: not-allowed; }
  .hke-btn.hke-ghost { background: none; border: 1px solid #caa14d; color: #ffd76a; }

  .hke-shop-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .hke-item {
    background: #241a0f; border: 1px solid #3a2712; border-radius: 12px; padding: 10px; text-align: center;
  }
  .hke-item .hke-item-name { font-size: 13px; margin-bottom: 6px; min-height: 32px; }
  .hke-item .hke-item-price { font-size: 12px; color: #ffd76a; margin-bottom: 8px; }

  .hke-wheel-wrap { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 10px 0 4px; }
  .hke-wheel { width: 220px; height: 220px; border-radius: 50%; position: relative; transition: transform 3.2s cubic-bezier(.17,.67,.16,1); }
  .hke-wheel-pointer { position: absolute; top: -6px; left: 50%; transform: translateX(-50%); font-size: 20px; }
  .hke-wheel-result { font-size: 14px; min-height: 20px; }

  .hke-boxes { display: flex; gap: 10px; justify-content: center; padding: 6px 0; }
  .hke-box {
    flex: 1; text-align: center; background: #241a0f; border: 1px solid #3a2712; border-radius: 12px; padding: 14px 8px; cursor: pointer;
  }
  .hke-box .hke-box-icon { font-size: 26px; }
  .hke-box .hke-box-name { font-size: 12px; margin: 6px 0 2px; }
  .hke-box .hke-box-cost { font-size: 12px; color: #ffd76a; }

  .hke-toast {
    position: fixed; bottom: 90px; inset-inline-end: 18px; z-index: 10000;
    background: #241a0f; border: 1px solid #caa14d; color: #f3e3c0;
    padding: 10px 16px; border-radius: 10px; font-size: 13px;
    opacity: 0; transform: translateY(6px); transition: all .25s ease;
    direction: rtl;
  }
  .hke-toast.hke-show { opacity: 1; transform: translateY(0); }
  `;

  const WHEEL_SEGMENTS = 8; // must match hokm_economy.WHEEL_PRIZES length on the server

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

  class EconomyPanel {
    constructor() {
      this.ws = null;
      this.wallet = { coins: 0, gems: 0, xp: 0, level: 1 };
      this.inventory = [];
      this.missions = [];
      this.shop = [];
      this.canSpinWheel = true;
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => this._send({ type: "get_economy" });
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

      switch (msg.type) {
        case "economy_state":
          this.wallet = msg.wallet;
          this.inventory = msg.inventory || [];
          this.missions = msg.missions || [];
          this.shop = msg.shop || [];
          this.canSpinWheel = !!msg.canSpinWheel;
          this._renderAll();
          break;
        case "economy_update":
          this.wallet = msg.wallet;
          this.missions = msg.missions || this.missions;
          this._renderAll();
          if (msg.reason === "match_end") {
            const r = msg.reward || {};
            let text = t('eco_match_reward','پاداش بازی: {coins} سکه').replace('{coins}', r.coins || 0);
            if (r.gems) text += t('eco_gems_suffix','، {gems} جم').replace('{gems}', r.gems);
            if (msg.leveledUp) text += t('eco_leveled_up',' — لول‌آپ شدی! 🎉');
            this._toast(text);
          }
          break;
        case "claim_mission_result":
          if (!msg.ok) this._toast(msg.error || t('eco_claim_error','خطا در دریافت جایزه'));
          break;
        case "spin_wheel_result":
          this._handleWheelResult(msg);
          break;
        case "buy_item_result":
          this._toast(msg.ok ? t('eco_bought','خریداری شد: {name}').replace('{name}', msg.item.name) : (msg.error || t('eco_buy_error','خطا در خرید')));
          break;
        case "open_box_result":
          if (msg.ok) {
            const r = msg.reward;
            let text = t('eco_box_reward','از جعبه گرفتی: {coins} سکه').replace('{coins}', r.coins);
            if (r.gems) text += t('eco_box_reward_gems',' + {gems} جم').replace('{gems}', r.gems);
            this._toast(text);
          } else {
            this._toast(msg.error || t('eco_box_error','خطا در باز کردن جعبه'));
          }
          break;
      }
    }

    _build() {
      injectStyle();

      // floating button
      this.fab = el("div", "hke-fab");
      this.fab.innerHTML = `
        <span class="hke-chip">🪙 <span data-coins>0</span></span>
        <span class="hke-chip">💎 <span data-gems>0</span></span>
        <span class="hke-lvl">Lv <span data-level>1</span></span>
      `;
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      // overlay + modal
      this.overlay = el("div", "hke-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hke-modal");
      modal.innerHTML = `
        <div class="hke-head">
          <h2>💰 ${t('eco_title','اقتصاد بازی')}</h2>
          <button class="hke-close" type="button">×</button>
        </div>
        <div class="hke-wallet-row">
          <span>🪙 <b data-w-coins>0</b> ${t('eco_coins_label','سکه')}</span>
          <span>💎 <b data-w-gems>0</b> ${t('eco_gems_label','جم')}</span>
          <span>⭐ ${t('eco_level_label','لول')} <b data-w-level>1</b></span>
        </div>
        <div class="hke-xpbar-wrap">
          <div class="hke-xpbar"><div data-xp-fill style="width:0%"></div></div>
          <div class="hke-xptext" data-xp-text></div>
        </div>
        <div class="hke-tabs">
          <button class="hke-tab hke-active" data-tab="missions">${t('eco_tab_missions','ماموریت‌ها')}</button>
          <button class="hke-tab" data-tab="shop">${t('eco_tab_shop','فروشگاه')}</button>
          <button class="hke-tab" data-tab="wheel">${t('eco_tab_wheel','گردونه شانس')}</button>
          <button class="hke-tab" data-tab="boxes">${t('eco_tab_boxes','جعبه‌ها')}</button>
        </div>
        <div class="hke-body">
          <div class="hke-panel hke-active" data-panel="missions"></div>
          <div class="hke-panel" data-panel="shop"></div>
          <div class="hke-panel" data-panel="wheel"></div>
          <div class="hke-panel" data-panel="boxes"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);

      modal.querySelector(".hke-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hke-tab").forEach((tab) => {
        tab.addEventListener("click", () => this._switchTab(tab.dataset.tab));
      });

      this.modal = modal;
      this.toastEl = el("div", "hke-toast");
      document.body.appendChild(this.toastEl);
    }

    open() { this.overlay.classList.add("hke-open"); this._send({ type: "get_economy" }); }
    close() { this.overlay.classList.remove("hke-open"); }

    _switchTab(name) {
      this.modal.querySelectorAll(".hke-tab").forEach((t) => t.classList.toggle("hke-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hke-panel").forEach((p) => p.classList.toggle("hke-active", p.dataset.panel === name));
    }

    _toast(text) {
      this.toastEl.textContent = text;
      this.toastEl.classList.add("hke-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toastEl.classList.remove("hke-show"), 3200);
    }

    _renderAll() {
      this._renderFab();
      this._renderWalletHeader();
      this._renderMissions();
      this._renderShop();
      this._renderWheel();
      this._renderBoxes();
    }

    _renderFab() {
      this.fab.querySelector("[data-coins]").textContent = this.wallet.coins;
      this.fab.querySelector("[data-gems]").textContent = this.wallet.gems;
      this.fab.querySelector("[data-level]").textContent = this.wallet.level;
    }

    _renderWalletHeader() {
      this.modal.querySelector("[data-w-coins]").textContent = this.wallet.coins;
      this.modal.querySelector("[data-w-gems]").textContent = this.wallet.gems;
      this.modal.querySelector("[data-w-level]").textContent = this.wallet.level;
      // XP bar: needs xp-required-for-next-level, which we don't get directly —
      // approximate with the same curve the server uses (100 + (level-1)*40).
      const need = 100 + (this.wallet.level - 1) * 40;
      const pct = Math.min(100, Math.round((this.wallet.xp / need) * 100));
      this.modal.querySelector("[data-xp-fill]").style.width = pct + "%";
      this.modal.querySelector("[data-xp-text]").textContent = t('eco_xp_to_next','{xp} / {need} XP تا لول بعد').replace('{xp}', this.wallet.xp).replace('{need}', need);
    }

    _renderMissions() {
      const panel = this.modal.querySelector('[data-panel="missions"]');
      panel.innerHTML = "";
      if (!this.missions.length) {
        panel.appendChild(el("div", null, t('eco_no_missions','ماموریتی برای امروز نیست.')));
        return;
      }
      this.missions.forEach((m) => {
        const pct = Math.min(100, Math.round((m.progress / m.target) * 100));
        const card = el("div", "hke-mission");
        card.innerHTML = `
          <div class="hke-mission-top"><span>${m.title}</span><span>${m.progress}/${m.target}</span></div>
          <div class="hke-mission-bar"><div style="width:${pct}%"></div></div>
          <div class="hke-mission-bottom">
            <span>🪙 ${m.rewardCoins} + ⭐ ${m.rewardXp}xp</span>
            <button class="hke-btn" ${m.claimed || m.progress < m.target ? "disabled" : ""} data-mission="${m.id}">
              ${m.claimed ? t('eco_mission_claimed','دریافت شد') : t('eco_mission_claim','دریافت جایزه')}
            </button>
          </div>
        `;
        card.querySelector("button").addEventListener("click", () => {
          this._send({ type: "claim_mission", missionId: m.id });
        });
        panel.appendChild(card);
      });
    }

    _renderShop() {
      const panel = this.modal.querySelector('[data-panel="shop"]');
      panel.innerHTML = "";
      const grid = el("div", "hke-shop-grid");
      this.shop.forEach((item) => {
        const owned = this.inventory.includes(item.id);
        const icon = item.currency === "gems" ? "💎" : "🪙";
        const card = el("div", "hke-item");
        card.innerHTML = `
          <div class="hke-item-name">${item.name}</div>
          <div class="hke-item-price">${icon} ${item.price}</div>
          <button class="hke-btn ${owned ? "hke-ghost" : ""}" ${owned ? "disabled" : ""} data-item="${item.id}">
            ${owned ? t('eco_owned','خریداری شده') : t('eco_buy','خرید')}
          </button>
        `;
        card.querySelector("button").addEventListener("click", () => {
          this._send({ type: "buy_item", itemId: item.id });
        });
        grid.appendChild(card);
      });
      panel.appendChild(grid);
    }

    _renderWheel() {
      const panel = this.modal.querySelector('[data-panel="wheel"]');
      panel.innerHTML = "";
      const wrap = el("div", "hke-wheel-wrap");
      const colors = ["#caa14d", "#7a5a26", "#caa14d", "#7a5a26", "#caa14d", "#7a5a26", "#ffd76a", "#a9302f"];
      const gradient = colors.map((c, i) => `${c} ${(i * 360) / WHEEL_SEGMENTS}deg ${((i + 1) * 360) / WHEEL_SEGMENTS}deg`).join(",");
      wrap.innerHTML = `
        <div style="position:relative">
          <div class="hke-wheel-pointer">🔻</div>
          <div class="hke-wheel" data-wheel style="background: conic-gradient(${gradient})"></div>
        </div>
        <button class="hke-btn" data-spin ${this.canSpinWheel ? "" : "disabled"}>
          ${this.canSpinWheel ? t('eco_spin_free','بچرخون! (رایگان، یک بار در روز)') : t('eco_spin_done','امروز چرخوندی — فردا بیا')}
        </button>
        <div class="hke-wheel-result" data-wheel-result></div>
      `;
      wrap.querySelector("[data-spin]").addEventListener("click", () => {
        this._send({ type: "spin_wheel" });
      });
      panel.appendChild(wrap);
      this._wheelEl = wrap.querySelector("[data-wheel]");
      this._wheelResultEl = wrap.querySelector("[data-wheel-result]");
    }

    _handleWheelResult(msg) {
      if (!msg.ok) {
        this._toast(msg.error || t('eco_cant_spin','نمیشه چرخوند'));
        return;
      }
      if (this._wheelEl) {
        const segAngle = 360 / WHEEL_SEGMENTS;
        const target = 360 * 4 + msg.prizeIndex * segAngle + segAngle / 2;
        this._wheelEl.style.transform = `rotate(${target}deg)`;
      }
      if (this._wheelResultEl) {
        this._wheelResultEl.textContent = t('eco_won_prize','بردی: {label} 🎉').replace('{label}', msg.label);
      }
      this.canSpinWheel = false;
      this._toast(t('eco_wheel_prize_toast','جایزه گردونه: {label}').replace('{label}', msg.label));
    }

    _renderBoxes() {
      const panel = this.modal.querySelector('[data-panel="boxes"]');
      panel.innerHTML = "";
      const boxes = [
        { key: "bronze", icon: "📦", name: t('eco_box_bronze','جعبه برنزی'), cost: 10 },
        { key: "silver", icon: "🎁", name: t('eco_box_silver','جعبه نقره‌ای'), cost: 25 },
        { key: "gold", icon: "🏆", name: t('eco_box_gold','جعبه طلایی'), cost: 60 },
      ];
      const row = el("div", "hke-boxes");
      boxes.forEach((b) => {
        const box = el("div", "hke-box");
        box.innerHTML = `
          <div class="hke-box-icon">${b.icon}</div>
          <div class="hke-box-name">${b.name}</div>
          <div class="hke-box-cost">💎 ${b.cost}</div>
        `;
        box.addEventListener("click", () => this._send({ type: "open_box", boxType: b.key }));
        row.appendChild(box);
      });
      panel.appendChild(row);
    }
  }

  const instance = new EconomyPanel();
  window.HokmEconomy = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
