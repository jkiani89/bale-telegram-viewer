"""
اسکریپت پاسخ‌دهی به /start در ربات بله (اختیاری)
اگر این اسکریپت را اجرا کنید، به هر کاربری که در ربات /start بفرستد،
یک پیام خوش‌آمدگویی به همراه دکمه شیشه‌ای مینی‌اپ ارسال می‌کند.
"""

import time
import requests

BALE_API = "https://tapi.bale.ai"
TOKEN = "1428241446:Sgux--r9MubQCm2JEoBLA2uW00ful-9T1fI"
MINIAPP_URL = "https://jkiani89.github.io/bale-telegram-viewer/"


def send_welcome_message(chat_id):
    url = f"{BALE_API}/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "سلام! 👋\nبه تلگرام ریدر در بله خوش آمدید.\nبرای مطالعه پست‌های کانال‌های عمومی تلگرام بدون نیاز به فیلترشکن، روی دکمه زیر کلیک کنید:",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "باز کردن",
                        "web_app": {"url": MINIAPP_URL}
                    }
                ]
            ]
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")


def main():
    print(f"🤖 ربات @bletgrmbot در حال گوش دادن به پیام‌هاست...")
    print(f"🔗 آدرس مینی‌اپ: {MINIAPP_URL}")
    last_update_id = 0

    while True:
        try:
            url = f"{BALE_API}/bot{TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            resp = requests.get(url, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")

                    if chat_id:
                        print(f"پیام جدید از {chat_id}: {text}")
                        send_welcome_message(chat_id)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nتوقف ربات.")
            break
        except Exception as e:
            print(f"خطا در ارتباط: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
