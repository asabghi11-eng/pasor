/*!
 * social-panel.js — Phase 7 UI for Hokm (چت داخل بازی، ایموجی، دوستان،
 * باشگاه/Clan، هدیه دادن).
 *
 * چرا این فایل جداست:
 * درست مثل economy-panel.js، این پنل کاملاً مستقل (self-contained) نوشته
 * شده تا بدون دست‌زدن به hokm-phase4-online.html اصلی، فقط با یک خط
 * وصل بشه.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body>:
 *        <script src="social-panel.js"></script>
 *   3) دقیقاً همون جایی که وب‌ساکت رو می‌سازی، یک خط زیرش اضافه کن:
 *        HokmSocial.attach(ws);
 *      (می‌تونه دقیقاً کنار HokmEconomy.attach(ws) باشه.)
 *
 * سرور (server.py) از قبل این پیام‌ها رو پشتیبانی می‌کنه:
 *   chat_message / quick_chat / emoji / chat (broadcast)
 *   add_friend / get_friends / friends_list
 *   spectate_room / leave_spectate (spectatorCount در game_state)
 * و این فایل، همراه با پچ فاز ۷ روی server.py، این‌ها رو هم اضافه می‌کنه:
 *   create_clan / join_clan / leave_clan / get_clan / clan_state
 *   send_gift / gift_sent / gift_received / gift_error
 */
(function () {
  "use strict";

  const CSS = `
  .hks-fab {
    position: fixed; bottom: calc(18px + env(safe-area-inset-bottom)); inset-inline-start: calc(18px + env(safe-area-inset-left)); z-index: 9998;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #0f1a24, #12273a);
    border: 1px solid #4d9dca; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #d9f0ff; user-select: none;
    transition: transform .15s ease;
  }
  @media (hover:hover) and (pointer:fine){ .hks-fab:hover { transform: translateY(-2px); } }
  @media (max-width:640px){
    .hks-fab{
      bottom: calc(88px + env(safe-area-inset-bottom));
      inset-inline-start: calc(10px + env(safe-area-inset-left));
      padding:6px 10px; gap:6px; font-size:12px;
    }
  }
  .hks-badge {
    background: #e2574c; color: #fff; font-weight: 700; font-size: 11px;
    border-radius: 999px; padding: 1px 7px; display: none;
  }
  .hks-badge.hks-show { display: inline-block; }

  .hks-overlay {
    position: fixed; inset: 0; background: rgba(6,10,14,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hks-overlay.hks-open { display: flex; }
  .hks-modal {
    width: min(92vw, 460px); max-height: 86vh; overflow: hidden;
    background: #0e161d; border: 1px solid #4d9dca; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #d9f0ff; direction: rtl;
  }
  .hks-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px; border-bottom: 1px solid #1c2e3d;
    background: linear-gradient(135deg, #12222f, #0e161d);
  }
  .hks-head h2 { margin: 0; font-size: 16px; }
  .hks-close { cursor: pointer; font-size: 20px; line-height: 1; color: #b7d4e6; background: none; border: none; width:44px; height:44px; display:flex; align-items:center; justify-content:center; margin:-10px; }
  .hks-tabs { display: flex; border-bottom: 1px solid #1c2e3d; flex-wrap: wrap; }
  .hks-tab { flex: 1; text-align: center; padding: 9px 4px; cursor: pointer; font-size: 13px; color: #8ba9bd; border-bottom: 2px solid transparent; min-width: 70px; }
  .hks-tab.hks-active { color: #4d9dca; border-bottom-color: #4d9dca; }
  .hks-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
  .hks-panel { display: none; }
  .hks-panel.hks-active { display: block; }

  .hks-chat-log { height: 220px; overflow-y: auto; background: #0a1015; border-radius: 10px; padding: 8px; margin-bottom: 8px; font-size: 13px; }
  .hks-chat-line { margin-bottom: 6px; }
  .hks-chat-line b { color: #4d9dca; }
  .hks-report-btn { cursor: pointer; margin-right: 6px; opacity: .5; font-size: 12px; }
  .hks-report-btn:hover { opacity: 1; }
  .hks-chat-row { display: flex; gap: 6px; }
  .hks-chat-row input { flex: 1; border-radius: 8px; border: 1px solid #1c2e3d; background: #0a1015; color: #d9f0ff; padding: 8px; font-family: inherit; font-size: 16px; }
  .hks-chat-row button { border: none; border-radius: 8px; background: #4d9dca; color: #06232f; font-weight: 700; padding: 8px 12px; cursor: pointer; }
  .hks-quick-row, .hks-emoji-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
  .hks-quick-row span, .hks-emoji-row span {
    cursor: pointer; background: #12222f; border: 1px solid #1c2e3d; border-radius: 999px;
    padding: 5px 10px; font-size: 12px;
  }
  .hks-note { color: #8ba9bd; font-size: 12px; text-align: center; padding: 20px 0; }

  .hks-list-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 4px; border-bottom: 1px solid #1c2e3d; font-size: 13px; }
  .hks-dot { width: 8px; height: 8px; border-radius: 999px; background: #556; display: inline-block; margin-inline-end: 6px; }
  .hks-dot.hks-online { background: #57d17a; }
  .hks-row-actions button { border: none; border-radius: 8px; background: #1c2e3d; color: #d9f0ff; padding: 5px 10px; font-size: 12px; cursor: pointer; }

  .hks-field { display: flex; gap: 6px; margin-bottom: 10px; }
  .hks-field input { flex: 1; border-radius: 8px; border: 1px solid #1c2e3d; background: #0a1015; color: #d9f0ff; padding: 8px; font-family: inherit; font-size: 16px; }
  .hks-field button { border: none; border-radius: 8px; background: #4d9dca; color: #06232f; font-weight: 700; padding: 8px 12px; cursor: pointer; }
  .hks-clan-card { background: #12222f; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
  .hks-clan-card .hks-code { font-family: monospace; letter-spacing: 2px; color: #ffd76a; }

  .hks-toast {
    position: fixed; bottom: 80px; inset-inline-start: 18px; z-index: 10000;
    background: #12222f; border: 1px solid #4d9dca; color: #d9f0ff;
    padding: 10px 16px; border-radius: 10px; font-size: 13px;
    opacity: 0; transform: translateY(8px); transition: all .2s ease; pointer-events: none;
  }
  .hks-toast.hks-show { opacity: 1; transform: translateY(0); }
  `;

  function quickChatPhrases() {
    return [
      t('soc_qc_0','دمت گرم!'), t('soc_qc_1','آفرین :)'), t('soc_qc_2','بد شانسی!'),
      t('soc_qc_3','حکم خوبی بود'), t('soc_qc_4','دوباره بازی می‌کنیم؟'), t('soc_qc_5','خیلی خوب بود!'),
    ];
  }
  const EMOJIS = ["👍", "😂", "😮", "😢", "🔥", "🎉", "🤝", "😅"];

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

  class SocialPanel {
    constructor() {
      this.ws = null;
      this.inRoom = false;
      this.myPlayerId = null;
      this.chatLines = [];
      this.friends = [];
      this.clan = null;
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      ws.addEventListener("open", () => this._send({ type: "get_friends" }));
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
        case "game_state":
          this.inRoom = true;
          this._renderChatAvailability();
          break;
        case "screen":
          if (msg.name === "lobby") { this.inRoom = false; this._renderChatAvailability(); }
          break;
        case "chat":
          this.chatLines.push(msg);
          this.chatLines = this.chatLines.slice(-50);
          this._renderChat();
          if (!this.isOpen) this._bump();
          break;
        case "friends_list":
          this.friends = msg.friends || [];
          this._renderFriends();
          break;
        case "friend_added":
          this._toast(t('soc_friend_added','{name} به لیست دوستانت اضافه شد').replace('{name}', msg.name));
          this._send({ type: "get_friends" });
          break;
        case "clan_state":
          this.clan = msg.clan;
          this._renderClan();
          break;
        case "clan_error":
          this._toast(msg.message);
          break;
        case "gift_sent":
          this._toast(t('soc_gift_sent','{amount} سکه به {name} هدیه دادی').replace('{amount}', msg.amount).replace('{name}', msg.name));
          break;
        case "gift_received":
          this._toast(t('soc_gift_received','{name} به تو {amount} سکه هدیه داد! 🎁').replace('{name}', msg.name).replace('{amount}', msg.amount));
          break;
        case "gift_error":
          this._toast(msg.message);
          break;
        case "muted":
          this._toast(msg.reason || t('soc_muted','چت تو موقتاً محدود شده'));
          break;
        case "report_sent":
          this._toast(t('soc_report_sent','گزارش ثبت شد، ممنون از کمکت'));
          break;
        case "report_error":
          this._toast(msg.message);
          break;
      }
    }

    _bump() {
      this.badge.textContent = "•";
      this.badge.classList.add("hks-show");
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hks-fab");
      this.fab.innerHTML = `💬 ${t('soc_fab_label','چت و دوستان')} <span class="hks-badge" data-badge></span>`;
      this.badge = this.fab.querySelector("[data-badge]");
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hks-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hks-modal");
      modal.innerHTML = `
        <div class="hks-head">
          <h2>👥 ${t('soc_title','اجتماعی')}</h2>
          <button class="hks-close" type="button">×</button>
        </div>
        <div class="hks-tabs">
          <button class="hks-tab hks-active" data-tab="chat">${t('soc_tab_chat','چت')}</button>
          <button class="hks-tab" data-tab="friends">${t('soc_tab_friends','دوستان')}</button>
          <button class="hks-tab" data-tab="clan">${t('soc_tab_clan','باشگاه')}</button>
          <button class="hks-tab" data-tab="gift">${t('soc_tab_gift','هدیه')}</button>
        </div>
        <div class="hks-body">
          <div class="hks-panel hks-active" data-panel="chat"></div>
          <div class="hks-panel" data-panel="friends"></div>
          <div class="hks-panel" data-panel="clan"></div>
          <div class="hks-panel" data-panel="gift"></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);
      this.modal = modal;

      modal.querySelector(".hks-close").addEventListener("click", () => this.close());
      modal.querySelectorAll(".hks-tab").forEach((tab) => {
        tab.addEventListener("click", () => this._switchTab(tab.dataset.tab));
      });

      this.toastEl = el("div", "hks-toast");
      document.body.appendChild(this.toastEl);

      this._renderChat();
      this._renderFriends();
      this._renderClan();
      this._renderGift();
    }

    open() {
      this.overlay.classList.add("hks-open");
      this.isOpen = true;
      this.badge.classList.remove("hks-show");
    }
    close() { this.overlay.classList.remove("hks-open"); this.isOpen = false; }

    _switchTab(name) {
      this.modal.querySelectorAll(".hks-tab").forEach((t) => t.classList.toggle("hks-active", t.dataset.tab === name));
      this.modal.querySelectorAll(".hks-panel").forEach((p) => p.classList.toggle("hks-active", p.dataset.panel === name));
    }

    _toast(text) {
      this.toastEl.textContent = text;
      this.toastEl.classList.add("hks-show");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toastEl.classList.remove("hks-show"), 3200);
    }

    _renderChatAvailability() { this._renderChat(); }

    _renderChat() {
      const panel = this.modal.querySelector('[data-panel="chat"]');
      if (!this.inRoom) {
        panel.innerHTML = `<div class="hks-note">${t('soc_chat_unavailable','چت و ایموجی فقط داخل یک بازی فعال هستن — اول یک بازی شروع کن.')}</div>`;
        return;
      }
      panel.innerHTML = "";
      const log = el("div", "hks-chat-log");
      this.chatLines.forEach((c) => {
        const line = el("div", "hks-chat-line");
        line.innerHTML = c.kind === "emoji"
          ? `<b>${c.from}:</b> ${c.emoji}`
          : `<b>${c.from}:</b> ${c.text}`;
        if (c.playerId && c.playerId !== this.myPlayerId) {
          const reportBtn = el("span", "hks-report-btn", "🚩");
          reportBtn.title = t('soc_report_title','گزارش این بازیکن');
          reportBtn.addEventListener("click", () => {
            this._send({ type: "report_player", playerId: c.playerId, reason: "abusive_chat" });
          });
          line.appendChild(reportBtn);
        }
        log.appendChild(line);
      });
      panel.appendChild(log);
      log.scrollTop = log.scrollHeight;

      const quickRow = el("div", "hks-quick-row");
      quickChatPhrases().forEach((phrase, idx) => {
        const s = el("span", null, phrase);
        s.addEventListener("click", () => this._send({ type: "quick_chat", phraseIndex: idx }));
        quickRow.appendChild(s);
      });
      panel.appendChild(quickRow);

      const emojiRow = el("div", "hks-emoji-row");
      EMOJIS.forEach((em) => {
        const s = el("span", null, em);
        s.addEventListener("click", () => this._send({ type: "emoji", emoji: em }));
        emojiRow.appendChild(s);
      });
      panel.appendChild(emojiRow);

      const row = el("div", "hks-chat-row");
      const input = el("input");
      input.type = "text";
      input.placeholder = t('soc_msg_placeholder','پیام بنویس...');
      input.maxLength = 200;
      const btn = el("button", null, t('soc_send_btn','ارسال'));
      const sendText = () => {
        const text = input.value.trim();
        if (!text) return;
        this._send({ type: "chat_message", text });
        input.value = "";
      };
      btn.addEventListener("click", sendText);
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });
      row.appendChild(input);
      row.appendChild(btn);
      panel.appendChild(row);
    }

    _renderFriends() {
      const panel = this.modal.querySelector('[data-panel="friends"]');
      panel.innerHTML = "";

      const addRow = el("div", "hks-field");
      const input = el("input");
      input.type = "text";
      input.placeholder = t('soc_playerid_placeholder','آی‌دی بازیکن (playerId)');
      const btn = el("button", null, t('soc_add_btn','افزودن'));
      btn.addEventListener("click", () => {
        const id = input.value.trim();
        if (id) { this._send({ type: "add_friend", playerId: id }); input.value = ""; }
      });
      addRow.appendChild(input);
      addRow.appendChild(btn);
      panel.appendChild(addRow);

      if (this.myPlayerId) {
        const mine = el("div", "hks-note", t('soc_your_id','آی‌دی خودت (برای اشتراک با دوستت):') + ` <span style="font-family:monospace;color:#4d9dca">${this.myPlayerId}</span>`);
        mine.style.padding = "0 0 10px";
        panel.appendChild(mine);
      }

      if (!this.friends.length) {
        panel.appendChild(el("div", "hks-note", t('soc_no_friends','هنوز دوستی اضافه نکردی.')));
        return;
      }
      this.friends.forEach((f) => {
        const item = el("div", "hks-list-item");
        item.innerHTML = `
          <span><span class="hks-dot ${f.online ? "hks-online" : ""}"></span>${f.name}</span>
        `;
        panel.appendChild(item);
      });
    }

    _renderClan() {
      const panel = this.modal.querySelector('[data-panel="clan"]');
      panel.innerHTML = "";

      if (!this.clan) {
        const createRow = el("div", "hks-field");
        const nameInput = el("input");
        nameInput.type = "text";
        nameInput.placeholder = t('soc_clan_name_placeholder','نام باشگاه جدید');
        const createBtn = el("button", null, t('soc_create_btn','ساخت'));
        createBtn.addEventListener("click", () => {
          const name = nameInput.value.trim();
          if (name) this._send({ type: "create_clan", name });
        });
        createRow.appendChild(nameInput);
        createRow.appendChild(createBtn);
        panel.appendChild(createRow);

        const joinRow = el("div", "hks-field");
        const codeInput = el("input");
        codeInput.type = "text";
        codeInput.placeholder = t('soc_clan_code_placeholder','کد باشگاه دوستت');
        const joinBtn = el("button", null, t('soc_join_btn','پیوستن'));
        joinBtn.addEventListener("click", () => {
          const code = codeInput.value.trim();
          if (code) this._send({ type: "join_clan", code });
        });
        joinRow.appendChild(codeInput);
        joinRow.appendChild(joinBtn);
        panel.appendChild(joinRow);
        return;
      }

      const card = el("div", "hks-clan-card");
      card.innerHTML = `
        <div style="font-size:15px;font-weight:700;margin-bottom:4px;">${this.clan.name} — ${t('soc_clan_level','لول')} ${this.clan.level}</div>
        <div style="font-size:12px;color:#8ba9bd;margin-bottom:6px;">${t('soc_invite_code','کد دعوت:')} <span class="hks-code">${this.clan.code}</span></div>
        <div style="font-size:12px;">XP: ${this.clan.xp} / ${this.clan.xpNeeded}</div>
      `;
      panel.appendChild(card);

      this.clan.members.forEach((m) => {
        const item = el("div", "hks-list-item");
        item.innerHTML = `<span><span class="hks-dot ${m.online ? "hks-online" : ""}"></span>${m.name}${m.playerId === this.clan.ownerId ? " 👑" : ""}</span>`;
        panel.appendChild(item);
      });

      const leaveBtn = el("button", null, t('soc_leave_clan','خروج از باشگاه'));
      leaveBtn.style.cssText = "margin-top:10px;border:none;border-radius:8px;background:#e2574c;color:#fff;padding:8px 12px;cursor:pointer;width:100%;";
      leaveBtn.addEventListener("click", () => this._send({ type: "leave_clan" }));
      panel.appendChild(leaveBtn);
    }

    _renderGift() {
      const panel = this.modal.querySelector('[data-panel="gift"]');
      panel.innerHTML = `<div class="hks-note" style="padding-bottom:10px;">${t('soc_gift_note','فقط به دوستانت (که آنلاین هستن) میشه هدیه داد — روزی یک بار.')}</div>`;

      if (!this.friends.length) {
        panel.appendChild(el("div", "hks-note", t('soc_add_friend_first','اول یک دوست اضافه کن.')));
        return;
      }
      this.friends.forEach((f) => {
        const row = el("div", "hks-list-item");
        const amountInput = el("input");
        amountInput.type = "number";
        amountInput.min = "10"; amountInput.max = "200"; amountInput.value = "50";
        amountInput.style.cssText = "width:60px;border-radius:6px;border:1px solid #1c2e3d;background:#0a1015;color:#d9f0ff;padding:4px;";
        const sendBtn = el("button", null, '🎁 ' + t('soc_gift_btn','هدیه'));
        sendBtn.addEventListener("click", () => {
          this._send({ type: "send_gift", playerId: f.playerId, amount: parseInt(amountInput.value, 10) || 50 });
        });
        row.innerHTML = `<span>${f.name}</span>`;
        const actions = el("div", "hks-row-actions");
        actions.style.display = "flex"; actions.style.gap = "6px"; actions.style.alignItems = "center";
        actions.appendChild(amountInput);
        actions.appendChild(sendBtn);
        row.appendChild(actions);
        panel.appendChild(row);
      });
    }
  }

  const instance = new SocialPanel();
  window.HokmSocial = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
