/*!
 * monetization-panel.js — Phase 10 UI for Hokm (VIP، پس نبرد/Battle Pass،
 * فروشگاه جم، تماشای تبلیغ برای سکه).
 *
 * نصب (دقیقاً مثل economy-panel.js):
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body> اضافه کن:
 *        <script src="monetization-panel.js"></script>
 *   3) همون‌جایی که وب‌ساکت رو می‌سازی، یک خط زیرش اضافه کن:
 *        HokmMonetization.attach(ws);
 *      (می‌تونه قبل یا بعد از HokmEconomy.attach(ws) باشه، تداخلی ندارن،
 *      هر دو فقط addEventListener روی همون ws می‌زنن.)
 *
 * چیزی که خودش انجام می‌ده:
 *   - یک دکمه شناور 👑 گوشه صفحه (بالای دکمه اقتصاد) که پنل VIP/پس نبرد/
 *     فروشگاه جم/تبلیغ رو باز می‌کنه.
 *   - به monetization_state / economy_state / *_result پیام‌های سرور
 *     (server.py فاز ۱۰) گوش می‌ده و UI رو آپدیت می‌کنه.
 *
 * نکته صادقانه: خرید VIP و پک جم این‌جا صرفاً برای تست UI/UX است — فرض بر
 * اینه که پرداخت واقعی (زرین‌پال/بازار/Google Play Billing) قبل از رسیدن
 * پیام buy_vip/buy_gem_pack به سرور تایید شده. جزئیات در docstring بالای
 * hokm_monetization.py توضیح داده شده.
 */
(function () {
  "use strict";

  const CSS = `
  .hkm-fab {
    position: fixed; bottom: 68px; inset-inline-end: 18px; z-index: 9997;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #2a1230, #431a4d);
    border: 1px solid #c780e0; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #f3d9ff; user-select: none;
    transition: transform .15s ease;
  }
  .hkm-fab:hover { transform: translateY(-2px); }
  .hkm-fab .hkm-crown { font-size: 16px; }
  .hkm-fab .hkm-vip-badge {
    background: #ffd76a; color: #2a1230; font-weight: 700; font-size: 11px;
    border-radius: 999px; padding: 2px 7px;
  }

  .hkm-overlay {
    position: fixed; inset: 0; background: rgba(10,7,3,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hkm-overlay.hkm-open { display: flex; }
  .hkm-modal {
    width: min(94vw, 520px); max-height: 88vh; overflow: hidden;
    background: #1b0f1f; border: 1px solid #c780e0; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #f3d9ff; direction: rtl;
  }
  .hkm-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px; border-bottom: 1px solid #3a1d42;
    background: linear-gradient(135deg, #2a1230, #1b0f1f);
  }
  .hkm-head h2 { margin: 0; font-size: 16px; }
  .hkm-close { cursor: pointer; font-size: 20px; line-height: 1; color: #e6c8f5; background: none; border: none; }

  .hkm-tabs { display: flex; border-bottom: 1px solid #3a1d42; flex-wrap: wrap; }
  .hkm-tab {
    flex: 1; min-width: 25%; text-align: center; padding: 10px 4px; cursor: pointer;
    font-size: 13px; color: #c9a9d9; background: none; border: none; border-bottom: 2px solid transparent;
  }
  .hkm-tab.hkm-active { color: #ffd76a; border-color: #ffd76a; }
  .hkm-body { padding: 14px 16px; overflow-y: auto; flex: 1; }
  .hkm-panel { display: none; }
  .hkm-panel.hkm-active { display: block; }

  .hkm-card {
    background: #241329; border: 1px solid #3a1d42; border-radius: 12px;
    padding: 12px; margin-bottom: 10px;
  }
  .hkm-row { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .hkm-muted { color: #b79bc7; font-size: 12px; }
  .hkm-btn {
    background: linear-gradient(135deg,#c780e0,#8f4aad); color: #1b0f1f; border: none;
    border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 700; cursor: pointer;
    white-space: nowrap;
  }
  .hkm-btn:disabled { opacity: .4; cursor: not-allowed; }
  .hkm-btn.hkm-ghost { background: none; border: 1px solid #c780e0; color: #f3d9ff; }

  .hkm-vip-status { text-align: center; padding: 6px 0 14px; }
  .hkm-vip-status .hkm-vip-big { font-size: 32px; }
  .hkm-plan-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }

  .hkm-bp-progress-wrap { padding: 4px 0 14px; }
  .hkm-bp-bar { height: 10px; border-radius: 999px; background: #3a1d42; overflow: hidden; }
  .hkm-bp-bar > div { height: 100%; background: linear-gradient(90deg,#c780e0,#ffd76a); }
  .hkm-bp-text { font-size: 12px; color: #c9a9d9; margin-top: 6px; display: flex; justify-content: space-between; }
  .hkm-bp-tier { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .hkm-bp-tier-num {
    width: 30px; height: 30px; border-radius: 8px; background: #3a1d42;
    display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0;
  }
  .hkm-bp-tier-num.hkm-done { background: #ffd76a; color: #1b0f1f; }
  .hkm-bp-reward { flex: 1; background: #241329; border: 1px solid #3a1d42; border-radius: 10px; padding: 8px 10px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
  .hkm-bp-reward.hkm-locked { opacity: .5; }

  .hkm-gem-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .hkm-gem-item { text-align: center; }

  .hkm-ad-wrap { text-align: center; padding: 10px 0; }
  .hkm-ad-icon { font-size: 40px; margin-bottom: 8px; }

  .hkm-toast {
    position: fixed; bottom: 90px; inset-inline-end: 18px; z-index: 10000;
    background: #241329; border: 1px solid #c780e0; color: #f3d9ff;
    padding: 10px 16px; border-radius: 10px; font-size: 13px;
    opacity: 0; transform: translateY(6px); transition: all .25s ease;
    direction: rtl;
  }
  .hkm-toast.hkm-show { opacity: 1; transform: translateY(0); }
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

  function fmtHMS(totalSeconds) {
    const d = Math.floor(totalSeconds / 86400);
    const h = Math.floor((totalSeconds % 86400) / 3600);
    if (d > 0) return t('mon_days_hours','{d} روز و {h} ساعت').replace('{d}', d).replace('{h}', h);
    if (h > 0) return t('mon_hours','{h} ساعت').replace('{h}', h);
    return t('mon_less_than_hour','کمتر از ۱ ساعت');
  }

  class MonetizationPanel {
    constructor() {
      this.ws = null;
      this.wallet = { coins: 0, gems: 0 };
      this.vip = { active: false, secondsLeft: 0, plans: [], canClaimDaily: false, dailyBonusCoins: 0 };
      this.ads = { watchedToday: 0, maxPerDay: 5, rewardCoins: 0 };
      this.gemPacks = [];
      this.battlePass = { xp: 0, tier: 0, maxTier: 30, xpPerTier: 120, premium: false, premiumPriceGems: 0, tiers: [], claimedFree: [], claimedPremium: [] };
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      const request = () => this._send({ type: "get_monetization" });
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
        case "economy_update":
          this.wallet = msg.wallet || this.wallet;
          this._renderAll();
          break;
        case "monetization_state":
          this.vip = msg.vip;
          this.ads = msg.ads;
          this.gemPacks = msg.gemPacks || [];
          this.battlePass = msg.battlePass;
          this._renderAll();
          break;
        case "battle_pass_tier_up":
          this._toast(t('mon_bp_tier_up','مرحله جدید پس نبرد باز شد: مرحله {tier} 🎉').replace('{tier}', msg.tier));
          break;
        case "watch_ad_result":
          if (msg.ok) this._toast(t('mon_ad_reward','از تبلیغ گرفتی: {coins} سکه').replace('{coins}', msg.reward.coins));
          else this._toast(msg.error || t('mon_ad_unavailable','نمیشه الان تبلیغ دید'));
          break;
        case "buy_vip_result":
          if (msg.ok) this._toast(t('mon_vip_activated','VIP {plan} فعال شد!').replace('{plan}', msg.plan.fa));
          else this._toast(msg.error || t('mon_vip_buy_error','خطا در خرید VIP'));
          break;
        case "claim_vip_daily_result":
          if (msg.ok) this._toast(t('mon_vip_daily_reward','جایزه روزانه VIP: {coins} سکه').replace('{coins}', msg.reward.coins));
          else this._toast(msg.error || t('mon_vip_daily_error','خطا در دریافت جایزه VIP'));
          break;
        case "buy_gem_pack_result":
          if (msg.ok) this._toast(t('mon_gems_added','{gems} جم اضافه شد').replace('{gems}', msg.gemsGranted));
          else this._toast(msg.error || t('mon_gem_buy_error','خطا در خرید جم'));
          break;
        case "buy_battle_pass_premium_result":
          if (msg.ok) this._toast(t('mon_bp_premium_activated','پس پریمیوم فعال شد! 👑'));
          else this._toast(msg.error || t('mon_bp_premium_error','خطا در خرید پس پریمیوم'));
          break;
        case "claim_bp_reward_result":
          if (msg.ok) this._toast(t('mon_bp_reward_claimed','جایزه پس نبرد دریافت شد 🎁'));
          else this._toast(msg.error || t('mon_claim_error','خطا در دریافت جایزه'));
          break;
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hkm-fab");
      this.fab.innerHTML = `<span class="hkm-crown">👑</span><span>${t('mon_fab_label','VIP و پس نبرد')}</span><span class="hkm-vip-badge" data-vip-badge style="display:none">VIP</span>`;
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hkm-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hkm-modal");
      modal.innerHTML = `
        <div class="hkm-head">
          <h2>👑 ${t('mon_title','VIP و پس نبرد')}</h2>
          <button class="hkm-close" type="button">×</button>
        </div>
        <div class="hkm-tabs">
          <button class="hkm-tab hkm-active" data-tab="vip">VIP</button>
          <button class="hkm-tab" data-tab="battlepass">${t('mon_tab_battlepass','پس نبرد')}</button>
          <button class="hkm-tab" data-tab="gems">${t('mon_tab_gems','فروشگاه جم')}</button>
          <button class="hkm-tab" data-tab="ads">${t('mon_tab_ads','تبلیغ')}</button>
        </div>
        <div class="hkm-body">
          <div class="hkm-panel hkm-active" data-panel="vip"></div>
          <div class="hkm-panel" data-panel="battlepass"></div>
          <div class="hkm-panel" data-panel="gems"></div>
          <div class="hkm-panel" data-panel="ads"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);

      modal.querySelector(".hkm-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hkm-tab").forEach((tab) => {
        tab.addEventListener("click", () => this._switchTab(tab.dataset.tab));
      });

      this.modal = modal;
      this.toastEl = el("div", "hkm-toast");
      document.body.appendChild(this.toastEl);
    }

    open() { this.overlay.classList.add("hkm-open"); this._send({ type: "get_monetization" }); }
    close() { this.overlay.classList.remove("hkm-open"); }

    _switchTab(name) {
      this.modal.querySelectorAll(".hkm-tab").forEach((t) => t.classList.toggle("hkm-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hkm-panel").forEach((p) => p.classList.toggle("hkm-active", p.dataset.panel === name));
    }

    _toast(text) {
      this.toastEl.textContent = text;
      this.toastEl.classList.add("hkm-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toastEl.classList.remove("hkm-show"), 3200);
    }

    _renderAll() {
      this._renderFab();
      this._renderVip();
      this._renderBattlePass();
      this._renderGems();
      this._renderAds();
    }

    _renderFab() {
      const badge = this.fab.querySelector("[data-vip-badge]");
      badge.style.display = this.vip.active ? "inline-block" : "none";
    }

    _renderVip() {
      const panel = this.modal.querySelector('[data-panel="vip"]');
      panel.innerHTML = "";

      const status = el("div", "hkm-vip-status");
      if (this.vip.active) {
        status.innerHTML = `
          <div class="hkm-vip-big">👑</div>
          <div>${t('mon_vip_active','عضو VIP هستی — {time} باقی مانده').replace('{time}', fmtHMS(this.vip.secondsLeft))}</div>
        `;
      } else {
        status.innerHTML = `<div class="hkm-vip-big">🔓</div><div class="hkm-muted">${t('mon_vip_not_active','هنوز VIP نیستی')}</div>`;
      }
      panel.appendChild(status);

      const dailyCard = el("div", "hkm-card");
      dailyCard.innerHTML = `
        <div class="hkm-row">
          <div>
            <div>🎁 ${t('mon_vip_daily_title','جایزه روزانه VIP')}</div>
            <div class="hkm-muted">${t('mon_vip_daily_desc','{coins} سکه رایگان هر روز برای اعضای VIP').replace('{coins}', this.vip.dailyBonusCoins)}</div>
          </div>
          <button class="hkm-btn" data-vip-daily ${this.vip.active && this.vip.canClaimDaily ? "" : "disabled"}>
            ${!this.vip.active ? t('mon_vip_only','فقط VIP') : (this.vip.canClaimDaily ? t('mon_claim_btn','دریافت') : t('mon_claimed_btn','دریافت شد'))}
          </button>
        </div>
      `;
      dailyCard.querySelector("button").addEventListener("click", () => this._send({ type: "claim_vip_daily" }));
      panel.appendChild(dailyCard);

      panel.appendChild(el("div", "hkm-muted", t('mon_vip_perks','مزایای VIP: ۱٫۲۵× سکه و ۱٫۱۵× XP در پایان هر بازی، به‌علاوه جایزه روزانه.')));

      const grid = el("div", "hkm-plan-grid");
      (this.vip.plans || []).forEach((plan) => {
        const card = el("div", "hkm-card");
        card.innerHTML = `
          <div class="hkm-row">
            <div>
              <div>${plan.fa}</div>
              <div class="hkm-muted">${plan.priceToman.toLocaleString("fa-IR")} ${t('mon_toman','تومان')} (${plan.priceUSD}$)</div>
            </div>
            <button class="hkm-btn" data-plan="${plan.id}">${t('mon_buy_btn','خرید')}</button>
          </div>
        `;
        card.querySelector("button").addEventListener("click", () => {
          this._send({ type: "buy_vip", planId: plan.id });
        });
        grid.appendChild(card);
      });
      panel.appendChild(grid);
    }

    _renderBattlePass() {
      const panel = this.modal.querySelector('[data-panel="battlepass"]');
      panel.innerHTML = "";
      const bp = this.battlePass;

      const progressWrap = el("div", "hkm-bp-progress-wrap");
      const xpIntoTier = bp.xp - bp.tier * bp.xpPerTier;
      const pct = Math.min(100, Math.round((xpIntoTier / bp.xpPerTier) * 100));
      progressWrap.innerHTML = `
        <div class="hkm-bp-bar"><div style="width:${bp.tier >= bp.maxTier ? 100 : pct}%"></div></div>
        <div class="hkm-bp-text">
          <span>${t('mon_bp_tier_label','مرحله')} ${bp.tier} / ${bp.maxTier}</span>
          <span>${bp.premium ? t('mon_bp_premium_active','پریمیوم فعال 👑') : t('mon_bp_free_only','فقط رایگان')}</span>
        </div>
      `;
      panel.appendChild(progressWrap);

      if (!bp.premium) {
        const buyCard = el("div", "hkm-card");
        buyCard.innerHTML = `
          <div class="hkm-row">
            <div>
              <div>👑 ${t('mon_bp_buy_premium_title','خرید مسیر پریمیوم')}</div>
              <div class="hkm-muted">${t('mon_bp_buy_premium_desc','جوایز دو برابر بهتر در همه مراحل')}</div>
            </div>
            <button class="hkm-btn" data-buy-bp>💎 ${bp.premiumPriceGems}</button>
          </div>
        `;
        buyCard.querySelector("button").addEventListener("click", () => {
          this._send({ type: "buy_battle_pass_premium" });
        });
        panel.appendChild(buyCard);
      }

      (bp.tiers || []).forEach((tierInfo) => {
        const reached = bp.tier >= tierInfo.tier;
        const row = el("div", "hkm-bp-tier");
        const freeClaimed = bp.claimedFree.includes(tierInfo.tier);
        const premClaimed = bp.claimedPremium.includes(tierInfo.tier);

        const freeRewardText = this._rewardText(tierInfo.freeReward);
        const premRewardText = this._rewardText(tierInfo.premiumReward);

        row.innerHTML = `
          <div class="hkm-bp-tier-num ${reached ? "hkm-done" : ""}">${tierInfo.tier}</div>
          <div class="hkm-bp-reward ${reached ? "" : "hkm-locked"}">
            <span>🆓 ${freeRewardText}</span>
            <button class="hkm-btn hkm-ghost" data-claim="free" ${reached && !freeClaimed ? "" : "disabled"}>
              ${freeClaimed ? t('mon_claimed_btn2','گرفته شد') : t('mon_claim_btn','دریافت')}
            </button>
          </div>
          <div class="hkm-bp-reward ${reached && bp.premium ? "" : "hkm-locked"}">
            <span>👑 ${premRewardText}</span>
            <button class="hkm-btn" data-claim="premium" ${reached && bp.premium && !premClaimed ? "" : "disabled"}>
              ${premClaimed ? t('mon_claimed_btn2','گرفته شد') : t('mon_claim_btn','دریافت')}
            </button>
          </div>
        `;
        row.querySelectorAll("[data-claim]").forEach((btn) => {
          btn.addEventListener("click", () => {
            this._send({ type: "claim_bp_reward", tier: tierInfo.tier, track: btn.dataset.claim });
          });
        });
        panel.appendChild(row);
      });
    }

    _rewardText(reward) {
      const parts = [];
      if (reward.coins) parts.push(`🪙${reward.coins}`);
      if (reward.gems) parts.push(`💎${reward.gems}`);
      if (reward.itemId) parts.push(`🎨 ${t('mon_special_item','آیتم ویژه')}`);
      return parts.join(" ") || "-";
    }

    _renderGems() {
      const panel = this.modal.querySelector('[data-panel="gems"]');
      panel.innerHTML = "";
      const grid = el("div", "hkm-gem-grid");
      (this.gemPacks || []).forEach((pack) => {
        const card = el("div", "hkm-card hkm-gem-item");
        card.innerHTML = `
          <div style="font-size:22px">💎 ${pack.gems}${pack.bonus ? ` <span class="hkm-muted">(+${pack.bonus} ${t('mon_bonus','هدیه')})</span>` : ""}</div>
          <div class="hkm-muted" style="margin:6px 0">${pack.priceToman.toLocaleString("fa-IR")} ${t('mon_toman','تومان')} (${pack.priceUSD}$)</div>
          <button class="hkm-btn" data-pack="${pack.id}">${t('mon_buy_btn','خرید')}</button>
        `;
        card.querySelector("button").addEventListener("click", () => {
          this._send({ type: "buy_gem_pack", packId: pack.id });
        });
        grid.appendChild(card);
      });
      panel.appendChild(grid);
    }

    _renderAds() {
      const panel = this.modal.querySelector('[data-panel="ads"]');
      panel.innerHTML = "";
      const remaining = this.ads.maxPerDay - this.ads.watchedToday;
      const wrap = el("div", "hkm-ad-wrap");
      wrap.innerHTML = `
        <div class="hkm-ad-icon">📺</div>
        <div>${t('mon_ad_prompt','یک تبلیغ کوتاه ببین و {coins} سکه بگیر').replace('{coins}', this.ads.rewardCoins)}</div>
        <div class="hkm-muted" style="margin:6px 0 12px">${t('mon_today','امروز:')} ${this.ads.watchedToday}/${this.ads.maxPerDay}</div>
        <button class="hkm-btn" data-watch-ad ${remaining > 0 ? "" : "disabled"}>
          ${remaining > 0 ? t('mon_watch_ad_btn','تماشای تبلیغ') : t('mon_ad_cap_reached','سقف امروز تمام شد')}
        </button>
      `;
      wrap.querySelector("button").addEventListener("click", () => this._send({ type: "watch_ad" }));
      panel.appendChild(wrap);
    }
  }

  const instance = new MonetizationPanel();
  window.HokmMonetization = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();