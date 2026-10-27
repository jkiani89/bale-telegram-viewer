"""
اسکریپت تعاملی راه‌اندازی سریع ربات بله (Zero-Server Quick Start).
این اسکریپت در چند ثانیه دکمه منوی ربات بله شما را به مینی‌اپ متصل می‌کند.
"""

import sys
import os
import requests

BALE_API_BASE = "https://tapi.bale.ai"


def main():
    print("=" * 60)
    print("🚀 راهنمای راه‌اندازی سریع ربات بله (Bale Telegram Viewer)")
    print("=" * 60)

    token = input("\n1️⃣ توکن ربات بله (دریافتی از @BotFather): ").strip()
    if not token:
        print("❌ توکن وارد نشد.")
        return

    # بررسی صحت توکن با getMe
    try:
        r = requests.get(f"{BALE_API_BASE}/bot{token}/getMe", timeout=10)
        data = r.json()
        if not data.get("ok"):
            print("❌ توکن ربات نامعتبر است یا ارتباط با بله برقرار نشد.")
            return
        bot_info = data.get("result", {})
        print(f"✅ ربات تایید شد: @{bot_info.get('username')} ({bot_info.get('first_name')})")
    except Exception as e:
        print(f"❌ خطا در اتصال به بله: {e}")
        return

    url_input = input("\n2️⃣ نام کاربری گیت‌هاب شما (یا لینک کامل GitHub Pages): ").strip()
    if not url_input:
        print("❌ آدرس وارد نشد.")
        return

    if url_input.startswith("http://") or url_input.startswith("https://"):
        miniapp_url = url_input.rstrip("/") + "/"
    else:
        # نام کاربری وارد شده
        miniapp_url = f"https://{url_input}.github.io/bale-telegram-viewer/"

    btn_text = input("\n3️⃣ عنوان دکمه منو در بله [پیش‌فرض: کانال‌های تلگرام]: ").strip()
    if not btn_text:
        btn_text = "کانال‌های تلگرام"

    print(f"\n[*] در حال تنظیم دکمه منوی ربات روی آدرس:\n👉 {miniapp_url} ...")

    api_url = f"{BALE_API_BASE}/bot{token}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": btn_text,
            "web_app": {
                "url": miniapp_url
            }
        }
    }

    try:
        resp = requests.post(api_url, json=payload, timeout=15)
        if resp.status_code == 200 and resp.json().get("ok"):
            print("\n" + "=" * 60)
            print("🎉 تبریک! ربات شما با موفقیت به مینی‌اپ متصل شد!")
            print(f"🔘 دکمه '{btn_text}' در کنار کادر چت ربات قرار گرفت.")
            print("📱 اکنون وارد اپلیکیشن بله شده و چت ربات خود را باز کنید.")
            print("=" * 60)
        else:
            print(f"❌ خطا از سمت بله: {resp.text}")
    except Exception as e:
        print(f"❌ خطای شبکه: {e}")


if __name__ == "__main__":
    main()
