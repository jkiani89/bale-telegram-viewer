"""
اسکریپت تنظیم یک‌باره ربات بله (Zero-Server Bale Bot Setup).
این اسکریپت با متد رسمی setChatMenuButton دکمه مینی‌اپ را برای همیشه در صفحه چت ربات فعال می‌کند
تا کاربر بدون نیاز به سرور همیشه روشن یا اجرای دائمی ربات، مستقیماً مینی‌اپ را باز کند.
"""

import argparse
import sys
import requests

BALE_API_BASE = "https://tapi.bale.ai"


def configure_bale_menu_button(bot_token, miniapp_url, button_text="کانال‌های تلگرام"):
    """
    تنظیم دکمه Menu Button برای ربات در بله
    """
    api_url = f"{BALE_API_BASE}/bot{bot_token}/setChatMenuButton"

    payload = {
        "menu_button": {
            "type": "web_app",
            "text": button_text,
            "web_app": {
                "url": miniapp_url
            }
        }
    }

    print(f"[*] در حال ارسال درخواست به {BALE_API_BASE}...")
    try:
        resp = requests.post(api_url, json=payload, timeout=15)
        data = resp.json()

        if resp.status_code == 200 and data.get("ok"):
            print("✅ دکمه مینی‌اپ با موفقیت روی ربات تنظیم شد!")
            print(f"🔗 آدرس مینی‌اپ: {miniapp_url}")
            print(f"🔘 متن دکمه: {button_text}")
            print("\nاکنون در اپلیکیشن بله وارد صفحه ربات خود شوید؛ دکمه در کنار کادر پیام ظاهر شده است.")
            return True
        else:
            print(f"❌ خطا از سمت سرور بله: {data}")
            return False

    except Exception as e:
        print(f"❌ خطای اتصال به سرور بله: {e}")
        return False


def send_test_inline_button(bot_token, chat_id, miniapp_url):
    """
    ارسال یک پیام تست حاوی دکمه شیشه‌ای (Inline Button) مینی‌اپ
    """
    api_url = f"{BALE_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "سلام! 👋\nبرای مشاهده پست‌های کانال‌های تلگرام بدون نیاز به فیلترشکن، روی دکمه زیر بزنید:",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "📱 ورود به تلگرام ریدر",
                        "web_app": {"url": miniapp_url}
                    }
                ]
            ]
        }
    }
    try:
        resp = requests.post(api_url, json=payload, timeout=15)
        print("ارسال پیام تست:", resp.json())
    except Exception as e:
        print(f"خطا در ارسال پیام تست: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="تنظیم منوی مینی‌اپ در ربات بله")
    parser.add_argument("--token", required=True, help="توکن ربات دریافتی از BotFather بله")
    parser.add_argument("--url", required=True, help="آدرس گیت‌هاب پیجز مینی‌اپ (مثال: https://user.github.io/repo/)")
    parser.add_argument("--text", default="کانال‌های تلگرام", help="متن دکمه منو")
    parser.add_argument("--test-chat-id", default=None, help="شناسه چت کاربری برای ارسال پیام تست اختیاری")

    args = parser.parse_args()

    success = configure_bale_menu_button(args.token, args.url, args.text)

    if success and args.test_chat_id:
        send_test_inline_button(args.token, args.test_chat_id, args.url)
