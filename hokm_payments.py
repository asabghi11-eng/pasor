"""
hokm_payments.py — real money via Zarinpal, sandbox by default.

server.py already had the calling code and the /pay/callback route
for this (search "request_payment" / "Zarinpal" in server.py) but
this module itself was missing from the project, so the server
couldn't even start (ImportError on `import hokm_payments as PAY`).
This file fills that gap.

Flow, honestly stated:
  1. Client asks to buy a VIP plan / gem pack -> request_payment()
     opens a payment "session" with Zarinpal and returns a pay_url.
  2. Client opens pay_url in a browser tab; the PERSON pays on
     Zarinpal's own page (we never see card details — that's the
     whole point of using a gateway).
  3. Zarinpal redirects back to our /pay/callback?Authority=...&Status=OK.
  4. server.py calls verify_payment() there, server-to-server, before
     granting anything. The purchase is ONLY ever granted from that
     verified callback — never trusted off what the client claims
     over the websocket.

SANDBOX BY DEFAULT: HOKM_ZARINPAL_SANDBOX defaults to "true", which
talks to sandbox.zarinpal.com — a real testing environment Zarinpal
runs where "payments" always succeed and no real money moves. That
means the app is fully runnable and testable for free, with zero
signup, before you ever touch real money.

To take REAL payments (costs nothing to set up, but now real money
moves and Zarinpal takes their fee per transaction — this is the one
part of the whole project that inherently isn't free once used for
real):
  1. Register a merchant account at https://www.zarinpal.com (needs
     an Iranian bank account / national ID — this is an Iran-specific
     gateway).
  2. Copy your real Merchant ID from the Zarinpal dashboard.
  3. export HOKM_ZARINPAL_MERCHANT_ID="your-real-merchant-id"
     export HOKM_ZARINPAL_SANDBOX="false"
  4. export HOKM_PUBLIC_BASE_URL="https://your-real-domain"  (Zarinpal
     needs a real https:// callback URL it can redirect back to —
     localhost will not work for real payments).

Amounts: Zarinpal's v4 API bills in Rials. The rest of this codebase
tracks prices in Tomans (1 Toman = 10 Rials), so this module converts
at the boundary — callers keep passing Tomans, nothing else in the
codebase needs to change.
"""
import os
import time
import uuid

SANDBOX = os.environ.get("HOKM_ZARINPAL_SANDBOX", "true").strip().lower() not in ("false", "0", "no")
MERCHANT_ID = os.environ.get(
    "HOKM_ZARINPAL_MERCHANT_ID",
    "00000000-0000-0000-0000-000000000000",  # Zarinpal's own documented sandbox merchant id
)

_HOST = "sandbox.zarinpal.com" if SANDBOX else "api.zarinpal.com"
_STARTPAY_HOST = "sandbox.zarinpal.com" if SANDBOX else "www.zarinpal.com"
REQUEST_URL = f"https://{_HOST}/pg/v4/payment/request.json"
VERIFY_URL = f"https://{_HOST}/pg/v4/payment/verify.json"
STARTPAY_URL = f"https://{_STARTPAY_HOST}/pg/StartPay/"

PENDING_EXPIRY_SECONDS = 30 * 60  # a payment session older than this is treated as abandoned


def is_expired(created_at: float, now: float = None) -> bool:
    now = now if now is not None else time.time()
    return (now - created_at) > PENDING_EXPIRY_SECONDS


def request_payment(amount_toman: int, description: str, callback_url: str, email: str = None, mobile: str = None) -> dict:
    """Opens a payment session. Returns:
      {"ok": True, "authority": "...", "pay_url": "..."} on success
      {"ok": False, "error": "..."} on failure (network issue, bad
      merchant id, amount below Zarinpal's minimum, etc.)

    Synchronous (uses `requests`, not an async HTTP client) to match
    how server.py already calls this — fine for the traffic an MVP
    sees, but worth swapping for an async client (httpx) if this
    server ever needs to handle many concurrent purchases without
    the event loop stalling for the ~1 request round-trip.
    """
    try:
        import requests
    except ImportError:
        return {"ok": False, "error": "پکیج requests نصب نیست — به requirements.txt اضافه شده، pip install دوباره بزن"}

    amount_rial = int(amount_toman) * 10
    payload = {
        "merchant_id": MERCHANT_ID,
        "amount": amount_rial,
        "description": description,
        "callback_url": callback_url,
    }
    if email:
        payload["metadata"] = {"email": email}
    if mobile:
        payload.setdefault("metadata", {})["mobile"] = mobile

    try:
        resp = requests.post(REQUEST_URL, json=payload, timeout=10)
        body = resp.json()
    except Exception as e:
        return {"ok": False, "error": f"اتصال به درگاه پرداخت برقرار نشد: {e}"}

    data = body.get("data") or {}
    errors = body.get("errors") or {}
    if errors or not data.get("authority") or data.get("code") != 100:
        msg = errors.get("message") if isinstance(errors, dict) else str(errors)
        return {"ok": False, "error": msg or "درخواست پرداخت رد شد"}

    authority = data["authority"]
    return {"ok": True, "authority": authority, "pay_url": STARTPAY_URL + authority}


def verify_payment(authority: str, amount_toman: int) -> dict:
    """Server-to-server confirmation that a payment actually went
    through, for the exact amount we expect. Returns:
      {"ok": True, "ref_id": "..."} on a genuinely completed payment
      {"ok": False, "error": "..."} otherwise — never grant a
      purchase on anything other than ok: True here.
    """
    try:
        import requests
    except ImportError:
        return {"ok": False, "error": "پکیج requests نصب نیست"}

    payload = {
        "merchant_id": MERCHANT_ID,
        "amount": int(amount_toman) * 10,
        "authority": authority,
    }
    try:
        resp = requests.post(VERIFY_URL, json=payload, timeout=10)
        body = resp.json()
    except Exception as e:
        return {"ok": False, "error": f"اتصال به درگاه پرداخت برقرار نشد: {e}"}

    data = body.get("data") or {}
    errors = body.get("errors") or {}
    # code 100 = freshly verified now; 101 = already verified earlier
    # for this authority (e.g. the person refreshed the callback page)
    # — both mean the payment is genuinely confirmed.
    if errors or data.get("code") not in (100, 101):
        msg = errors.get("message") if isinstance(errors, dict) else str(errors)
        return {"ok": False, "error": msg or "تایید پرداخت ناموفق بود"}

    return {"ok": True, "ref_id": data.get("ref_id")}
