#!/usr/bin/env python3
"""
check_payment_config.py — چک‌لیست قبل از رفتن روی پرداخت واقعی زرین‌پال.

کد پرداخت (hokm_payments.py) از قبل کامله؛ تنها چیزی که مونده تنظیم سه‌تا
متغیر محیطیه. این اسکریپت همون‌ها رو چک می‌کنه و می‌گه دقیقاً چی کم داری —
بدون نیاز به بالا آوردن کل سرور یا زدن یه پرداخت واقعی آزمایشی.

اجرا:
    python3 check_payment_config.py

اگه از .env استفاده می‌کنی، اول لودش کن:
    export $(grep -v '^#' .env | xargs) && python3 check_payment_config.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ok = True

    print("بررسی تنظیمات پرداخت زرین‌پال\n" + "-" * 40)

    sandbox = os.environ.get("HOKM_ZARINPAL_SANDBOX", "true").strip().lower() not in ("false", "0", "no")
    if sandbox:
        print("⚠️  HOKM_ZARINPAL_SANDBOX هنوز روی sandbox — پرداخت‌ها الکی موفق می‌شن، پول واقعی جابه‌جا نمی‌شه.")
        print("    برای پرداخت واقعی: export HOKM_ZARINPAL_SANDBOX=false")
        ok = False
    else:
        print("✅ HOKM_ZARINPAL_SANDBOX=false — حالت واقعی فعاله.")

    merchant_id = os.environ.get("HOKM_ZARINPAL_MERCHANT_ID", "").strip()
    sandbox_default_id = "00000000-0000-0000-0000-000000000000"
    if not merchant_id or merchant_id == sandbox_default_id:
        print("❌ HOKM_ZARINPAL_MERCHANT_ID ست نشده (یا هنوز مقدار پیش‌فرض سندباکسه).")
        print("    از داشبورد زرین‌پال (https://www.zarinpal.com) merchant ID واقعیت رو کپی کن.")
        ok = False
    else:
        print(f"✅ HOKM_ZARINPAL_MERCHANT_ID ست شده ({merchant_id[:8]}...).")

    base_url = os.environ.get("HOKM_PUBLIC_BASE_URL", "http://localhost:8000").strip()
    if base_url.startswith("http://localhost") or base_url.startswith("http://127."):
        print("❌ HOKM_PUBLIC_BASE_URL هنوز روی localhost — زرین‌پال نمی‌تونه به اینجا ریدایرکت کنه.")
        print("    یه دامنه‌ی https:// واقعی که از بیرون قابل‌دسترسیه بذار.")
        ok = False
    elif not base_url.startswith("https://"):
        print(f"⚠️  HOKM_PUBLIC_BASE_URL روی https نیست ({base_url}) — زرین‌پال معمولاً https لازم داره.")
        ok = False
    else:
        print(f"✅ HOKM_PUBLIC_BASE_URL ست شده ({base_url}).")

    dev_free = os.environ.get("HOKM_DEV_FREE_PURCHASES", "1").strip()
    if dev_free == "1":
        print("❌ HOKM_DEV_FREE_PURCHASES=1 — خریدها بدون پرداخت واقعی، رایگان انجام می‌شن!")
        print("    برای پروداکشن: export HOKM_DEV_FREE_PURCHASES=0")
        ok = False
    else:
        print("✅ HOKM_DEV_FREE_PURCHASES=0 — خرید رایگان تستی خاموشه.")

    print("-" * 40)
    if ok:
        print("✅ همه‌چی برای پرداخت واقعی آماده‌ست.")
        print("   یه توصیه: قبل از عمومی‌کردن، یه خرید واقعی کوچیک (مثلاً کمترین مبلغ) با کارت خودت بزن و مطمئن شو verify_payment درست تایید می‌کنه.")
    else:
        print("⛔ هنوز آماده نیست — مواردی که ❌/⚠️ گرفتن رو درست کن و دوباره اجرا کن.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
