/*!
 * voice-panel.js — Phase 14 UI for Hokm (چت صوتی داخل اتاق/بازی).
 *
 * همون الگوی بقیه‌ی پنل‌ها (economy/social/tournament/...): کاملاً مستقل
 * (self-contained)، فقط با یک خط وصل میشه.
 *
 * نصب:
 *   1) این فایل رو کنار hokm-phase4-online.html بذار.
 *   2) قبل از بسته‌شدن </body>:
 *        <script src="voice-panel.js"></script>
 *   3) همون جایی که وب‌ساکت رو می‌سازی:
 *        HokmVoice.attach(ws);
 *
 * معماری (صادقانه، مهم برای فهمیدن محدودیت‌ها):
 *   - سرور (server.py، پیام‌های voice_join/voice_leave/webrtc_offer/
 *     webrtc_answer/webrtc_ice) فقط signaling رو رله می‌کنه — هیچ‌وقت
 *     صدای واقعی رو نمی‌بینه، ضبط نمی‌کنه، حتی از خودش رد نمی‌کنه.
 *   - بین بازیکن‌های یک اتاق (حداکثر ۴ نفر) یک شبکه‌ی mesh از اتصالات
 *     WebRTC مستقیم (peer-to-peer) ساخته میشه — یعنی صدا مستقیم بین
 *     مرورگرها رد و بدل میشه، نه از سرور.
 *   - فقط از STUN عمومی گوگل استفاده شده (رایگان، بدون نیاز به تنظیم).
 *     STUN برای اکثر شبکه‌های خانگی/موبایل کافیه، ولی پشت NATهای
 *     سخت‌گیر/فایروال شرکتی معمولاً وصل نمیشه — برای اون حالت باید یک
 *     سرور TURN واقعی (که هزینه‌ی پهنای‌باند داره، رایگان نیست) اضافه
 *     کنی؛ ICE_SERVERS پایین همون جاییه که باید اضافه بشه.
 *   - چون حداکثر ۴ نفر در هر اتاق هستن، mesh (حداکثر ۶ اتصال) کاملاً
 *     کافیه و نیازی به یک سرور SFU جداگانه (مثل mediasoup/LiveKit)
 *     نیست.
 */
(function () {
  "use strict";

  // Public STUN only, by default — see the honesty note above. To add a
  // TURN server, push another entry here, e.g.:
  //   { urls: "turn:your-turn-host:3478", username: "...", credential: "..." }
  const ICE_SERVERS = [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
  ];

  const CSS = `
  .hkv-fab {
    position: fixed; bottom: 18px; inset-inline-end: 230px; z-index: 9998;
    display: flex; align-items: center; gap: 8px;
    background: linear-gradient(135deg, #10241a, #143a28);
    border: 1px solid #3fd68a; border-radius: 999px;
    padding: 8px 14px; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.4);
    font-family: inherit; color: #d7ffe9; user-select: none;
    transition: transform .15s ease;
  }
  .hkv-fab:hover { transform: translateY(-2px); }
  .hkv-fab.hkv-fab-active { border-color: #ffd76a; }
  .hkv-fab .hkv-fab-count {
    background: #3fd68a; color: #10241a; font-weight: 700; font-size: 11px;
    border-radius: 999px; padding: 1px 7px; display: none;
  }
  .hkv-fab.hkv-fab-active .hkv-fab-count { display: inline-block; }

  .hkv-overlay {
    position: fixed; inset: 0; background: rgba(6,10,12,.72);
    z-index: 9999; display: none; align-items: center; justify-content: center;
    backdrop-filter: blur(2px);
  }
  .hkv-overlay.hkv-open { display: flex; }
  .hkv-modal {
    width: min(92vw, 420px); max-height: 80vh; overflow: hidden;
    background: #0d2016; border: 1px solid #3fd68a; border-radius: 18px;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    font-family: inherit; color: #d7ffe9; direction: rtl;
  }
  .hkv-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #17422c; background: linear-gradient(135deg, #12291b, #0d2016); }
  .hkv-head h2 { margin: 0; font-size: 16px; }
  .hkv-close { cursor: pointer; font-size: 20px; line-height: 1; color: #a9e8c8; background: none; border: none; }
  .hkv-body { padding: 12px 16px; overflow-y: auto; flex: 1; }

  .hkv-toggle-btn {
    width: 100%; border: none; border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 700;
    cursor: pointer; margin-bottom: 12px; font-family: inherit;
    background: #3fd68a; color: #0d2016;
  }
  .hkv-toggle-btn.hkv-in-call { background: #d64d4d; color: #fff; }
  .hkv-toggle-btn:disabled { opacity: .4; cursor: not-allowed; }

  .hkv-mute-btn {
    width: 100%; border: 1px solid #3fd68a; background: none; color: #d7ffe9;
    border-radius: 10px; padding: 9px; font-size: 13px; cursor: pointer; margin-bottom: 12px; font-family: inherit;
  }
  .hkv-mute-btn.hkv-muted { border-color: #d64d4d; color: #ff9a9a; }
  .hkv-mute-btn:disabled { opacity: .4; cursor: not-allowed; }

  .hkv-note { color: #7ab598; font-size: 11px; text-align: center; padding: 6px 0 14px; line-height: 1.7; }

  .hkv-participants { display: flex; flex-direction: column; gap: 6px; }
  .hkv-p-row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #12291b; border-radius: 10px; font-size: 13px; }
  .hkv-p-dot { width: 9px; height: 9px; border-radius: 999px; background: #3fd68a; flex-shrink: 0; transition: box-shadow .1s ease; }
  .hkv-p-dot.hkv-speaking { box-shadow: 0 0 0 4px rgba(63,214,138,.35); }
  .hkv-p-name { flex: 1; }
  .hkv-p-you { color: #7ab598; font-size: 11px; }
  `;

  function injectStyle() {
    if (document.getElementById("hkv-style")) return;
    const s = document.createElement("style");
    s.id = "hkv-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  class VoicePanel {
    constructor() {
      this.ws = null;
      this.myPlayerId = null;
      this.myName = "";
      this.inRoom = false;
      this.inCall = false;
      this.muted = false;
      this.localStream = null;
      this.peers = new Map();       // playerId -> { pc, audioEl, analyser, speaking, name }
      this.pendingCandidates = new Map(); // playerId -> [candidate,...] queued before remote SDP is set
      this._build();
    }

    attach(ws) {
      this.ws = ws;
      ws.addEventListener("message", (ev) => this._onMessage(ev));
      ws.addEventListener("close", () => this._teardownAll());
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
        case "room_wait":
          this.inRoom = true;
          this._updateToggleAvailability();
          break;
        case "screen":
          if (msg.name === "lobby" || msg.name === "matchmaking") {
            this.inRoom = false;
            if (this.inCall) this._leaveCall();
            this._updateToggleAvailability();
          }
          break;
        case "muted":
          if (this.inCall) this._leaveCall();
          this._toast(t("voi_chat_muted", "چت صوتی تو موقتاً محدود شده"));
          break;
        case "voice_joined":
          this._onVoiceJoined(msg.peers || []);
          break;
        case "voice_peer_joined":
          this._registerPeerName(msg.playerId, msg.name);
          this._renderParticipants();
          break;
        case "voice_peer_left":
          this._closePeer(msg.playerId);
          this._renderParticipants();
          break;
        case "webrtc_offer":
          this._onOffer(msg.fromId, msg.fromName, msg.sdp);
          break;
        case "webrtc_answer":
          this._onAnswer(msg.fromId, msg.sdp);
          break;
        case "webrtc_ice":
          this._onIce(msg.fromId, msg.candidate);
          break;
      }
    }

    _build() {
      injectStyle();

      this.fab = el("div", "hkv-fab", `🎙️ ${t("voi_fab_label", "صوتی")}<span class="hkv-fab-count" data-count>0</span>`);
      this.fab.addEventListener("click", () => this.open());
      document.body.appendChild(this.fab);

      this.overlay = el("div", "hkv-overlay");
      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      const modal = el("div", "hkv-modal");
      modal.innerHTML = `
        <div class="hkv-head">
          <h2>🎙️ ${t("voi_title", "چت صوتی")}</h2>
          <button class="hkv-close" type="button">×</button>
        </div>
        <div class="hkv-body">
          <button class="hkv-toggle-btn" type="button" data-toggle disabled>${t("voi_join_btn", "پیوستن به صدا")}</button>
          <button class="hkv-mute-btn" type="button" data-mute style="display:none">🎤 ${t("voi_mute_btn", "بی‌صدا کردن خودم")}</button>
          <div class="hkv-note">${t(
            "voi_note",
            "این یک تماس صوتی مستقیم بین مرورگرهاست (WebRTC) — فقط داخل اتاق فعلی کار می‌کنه. پشت بعضی شبکه‌ها (مثل شبکه‌های شرکتی) ممکنه وصل نشه."
          )}</div>
          <div class="hkv-participants" data-participants></div>
        </div>
      `;
      this.overlay.appendChild(modal);
      document.body.appendChild(this.overlay);
      this.modal = modal;

      modal.querySelector(".hkv-close").addEventListener("click", () => this.close());
      this._toggleBtn = modal.querySelector("[data-toggle]");
      this._muteBtn = modal.querySelector("[data-mute]");
      this._participantsEl = modal.querySelector("[data-participants]");

      this._toggleBtn.addEventListener("click", () => {
        if (this.inCall) this._leaveCall(); else this._joinCall();
      });
      this._muteBtn.addEventListener("click", () => this._toggleMute());

      this.toastEl = el("div", "hkv-toast");
      Object.assign(this.toastEl.style, {
        position: "fixed", bottom: "18px", insetInlineEnd: "340px", zIndex: 10000,
        background: "#12291b", border: "1px solid #3fd68a", color: "#d7ffe9",
        padding: "10px 16px", borderRadius: "10px", fontSize: "13px", maxWidth: "260px",
        opacity: 0, transform: "translateY(8px)", transition: "all .2s ease", pointerEvents: "none",
      });
      document.body.appendChild(this.toastEl);
    }

    open() { this.overlay.classList.add("hkv-open"); this._updateToggleAvailability(); }
    close() { this.overlay.classList.remove("hkv-open"); }

    _toast(text) {
      if (!text) return;
      this.toastEl.textContent = text;
      this.toastEl.style.opacity = 1;
      this.toastEl.style.transform = "translateY(0)";
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        this.toastEl.style.opacity = 0;
        this.toastEl.style.transform = "translateY(8px)";
      }, 3600);
    }

    _updateToggleAvailability() {
      this._toggleBtn.disabled = !this.inRoom && !this.inCall;
    }

    _updateFab() {
      const count = this.peers.size + (this.inCall ? 1 : 0);
      this.fab.classList.toggle("hkv-fab-active", this.inCall);
      const badge = this.fab.querySelector("[data-count]");
      badge.textContent = count;
      this.fab.querySelector("[data-count]") && (badge.style.display = this.inCall ? "inline-block" : "none");
    }

    // ------------------------------------------------------------ call lifecycle --

    async _joinCall() {
      if (!this.inRoom || this.inCall) return;
      try {
        this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      } catch (e) {
        this._toast(t("voi_mic_denied", "دسترسی به میکروفون رد شد یا در دسترس نیست"));
        return;
      }
      this.inCall = true;
      this.muted = false;
      this._toggleBtn.textContent = t("voi_leave_btn", "خروج از صدا");
      this._toggleBtn.classList.add("hkv-in-call");
      this._muteBtn.style.display = "";
      this._muteBtn.classList.remove("hkv-muted");
      this._muteBtn.textContent = "🎤 " + t("voi_mute_btn", "بی‌صدا کردن خودم");
      this._updateFab();
      this._send({ type: "voice_join" });
    }

    _leaveCall() {
      if (!this.inCall) return;
      this._send({ type: "voice_leave" });
      this._teardownAll();
    }

    _teardownAll() {
      this.inCall = false;
      this._toggleBtn.textContent = t("voi_join_btn", "پیوستن به صدا");
      this._toggleBtn.classList.remove("hkv-in-call");
      this._muteBtn.style.display = "none";
      if (this.localStream) {
        this.localStream.getTracks().forEach((tr) => tr.stop());
        this.localStream = null;
      }
      for (const pid of Array.from(this.peers.keys())) this._closePeer(pid);
      this.pendingCandidates.clear();
      this._updateFab();
      this._renderParticipants();
      this._updateToggleAvailability();
    }

    _toggleMute() {
      if (!this.localStream) return;
      this.muted = !this.muted;
      this.localStream.getAudioTracks().forEach((tr) => { tr.enabled = !this.muted; });
      this._muteBtn.classList.toggle("hkv-muted", this.muted);
      this._muteBtn.textContent = (this.muted ? "🔇 " : "🎤 ") +
        (this.muted ? t("voi_unmute_btn", "برداشتن بی‌صدا") : t("voi_mute_btn", "بی‌صدا کردن خودم"));
    }

    // ------------------------------------------------------------- peer wiring --

    _registerPeerName(playerId, name) {
      const existing = this.peers.get(playerId);
      if (existing) { existing.name = name; return; }
      this.peers.set(playerId, { pc: null, audioEl: null, analyser: null, speaking: false, name });
    }

    _makePeerConnection(playerId) {
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      if (this.localStream) {
        this.localStream.getTracks().forEach((tr) => pc.addTrack(tr, this.localStream));
      }
      pc.onicecandidate = (e) => {
        if (e.candidate) this._send({ type: "webrtc_ice", targetId: playerId, candidate: e.candidate });
      };
      pc.ontrack = (e) => {
        const entry = this.peers.get(playerId);
        if (!entry) return;
        if (!entry.audioEl) {
          const audio = el("audio");
          audio.autoplay = true;
          document.body.appendChild(audio);
          entry.audioEl = audio;
        }
        entry.audioEl.srcObject = e.streams[0];
        this._wireSpeakingDetection(playerId, e.streams[0]);
      };
      pc.onconnectionstatechange = () => {
        if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
          // Leave cleanup to the explicit voice_peer_left message from the
          // server (it fires on real leave/disconnect); a flaky ICE hiccup
          // shouldn't nuke the UI entry on its own.
        }
      };
      const entry = this.peers.get(playerId) || { name: playerId };
      entry.pc = pc;
      this.peers.set(playerId, entry);
      return pc;
    }

    async _onVoiceJoined(existingPeers) {
      // We just joined; `existingPeers` were already in the call before us.
      // We are the initiator for each of these links (see server.py's
      // comment on voice_join for why only one side offers).
      for (const peer of existingPeers) {
        this._registerPeerName(peer.playerId, peer.name);
        const pc = this._makePeerConnection(peer.playerId);
        try {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          this._send({ type: "webrtc_offer", targetId: peer.playerId, sdp: pc.localDescription });
        } catch (e) { /* best-effort — a failed link just won't carry audio */ }
      }
      this._renderParticipants();
    }

    async _onOffer(fromId, fromName, sdp) {
      if (!this.inCall) return; // ignore signaling if we're not in the call ourselves
      this._registerPeerName(fromId, fromName);
      let entry = this.peers.get(fromId);
      const pc = (entry && entry.pc) || this._makePeerConnection(fromId);
      try {
        await pc.setRemoteDescription(new RTCSessionDescription(sdp));
        await this._flushPendingCandidates(fromId, pc);
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        this._send({ type: "webrtc_answer", targetId: fromId, sdp: pc.localDescription });
      } catch (e) { /* best-effort */ }
      this._renderParticipants();
    }

    async _onAnswer(fromId, sdp) {
      const entry = this.peers.get(fromId);
      if (!entry || !entry.pc) return;
      try {
        await entry.pc.setRemoteDescription(new RTCSessionDescription(sdp));
        await this._flushPendingCandidates(fromId, entry.pc);
      } catch (e) { /* best-effort */ }
    }

    async _onIce(fromId, candidate) {
      if (!candidate) return;
      const entry = this.peers.get(fromId);
      if (!entry || !entry.pc || !entry.pc.remoteDescription) {
        const q = this.pendingCandidates.get(fromId) || [];
        q.push(candidate);
        this.pendingCandidates.set(fromId, q);
        return;
      }
      try { await entry.pc.addIceCandidate(new RTCIceCandidate(candidate)); } catch (e) { /* best-effort */ }
    }

    async _flushPendingCandidates(playerId, pc) {
      const q = this.pendingCandidates.get(playerId);
      if (!q || !q.length) return;
      this.pendingCandidates.delete(playerId);
      for (const c of q) {
        try { await pc.addIceCandidate(new RTCIceCandidate(c)); } catch (e) { /* best-effort */ }
      }
    }

    _wireSpeakingDetection(playerId, stream) {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = this._audioCtx || (this._audioCtx = new AudioCtx());
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);
        const entry = this.peers.get(playerId);
        if (entry) entry.analyser = analyser;
        const tick = () => {
          const e = this.peers.get(playerId);
          if (!e || !e.analyser) return; // peer left, stop the loop
          e.analyser.getByteFrequencyData(data);
          const avg = data.reduce((a, b) => a + b, 0) / data.length;
          const speaking = avg > 12;
          if (speaking !== e.speaking) {
            e.speaking = speaking;
            this._renderParticipants();
          }
          requestAnimationFrame(tick);
        };
        tick();
      } catch (e) { /* speaking indicator is cosmetic — never block audio over it */ }
    }

    _closePeer(playerId) {
      const entry = this.peers.get(playerId);
      if (!entry) return;
      if (entry.pc) { try { entry.pc.close(); } catch (e) {} }
      if (entry.audioEl) { entry.audioEl.srcObject = null; entry.audioEl.remove(); }
      this.peers.delete(playerId);
      this.pendingCandidates.delete(playerId);
      this._updateFab();
    }

    _renderParticipants() {
      this._participantsEl.innerHTML = "";
      if (this.inCall) {
        const row = el("div", "hkv-p-row");
        row.innerHTML = `<span class="hkv-p-dot"></span><span class="hkv-p-name">${t("voi_you", "شما")}</span><span class="hkv-p-you">${this.muted ? "🔇" : "🎤"}</span>`;
        this._participantsEl.appendChild(row);
      }
      this.peers.forEach((entry, playerId) => {
        const row = el("div", "hkv-p-row");
        row.innerHTML = `<span class="hkv-p-dot${entry.speaking ? " hkv-speaking" : ""}"></span><span class="hkv-p-name">${entry.name || playerId}</span>`;
        this._participantsEl.appendChild(row);
      });
      this._updateFab();
    }
  }

  const instance = new VoicePanel();
  window.HokmVoice = {
    attach: (ws) => instance.attach(ws),
    open: () => instance.open(),
    close: () => instance.close(),
  };
})();
