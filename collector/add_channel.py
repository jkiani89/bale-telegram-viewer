"""
ماژول افزودن پویا و هوشمند کانال جدید به config/channels.json
بررسی پیش‌نمایش در تلگرام، استخراج عنوان کانال و فراخوانی اسکرپر.
"""

import argparse
import json
import logging
import os
import re
import sys
import requests
from bs4 import BeautifulSoup

# اطمینان از قرار گرفتن پوشه collector در مسیر ایمپورت‌ها
collector_dir = os.path.dirname(os.path.abspath(__file__))
if collector_dir not in sys.path:
    sys.path.insert(0, collector_dir)

try:
    from parser import parse_channel_page
    from main import run_collector
except ImportError:
    from collector.parser import parse_channel_page
    from collector.main import run_collector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AddChannel")


def clean_channel_id(raw_input):
    """پاکسازی آیدی کانال از @ یا لینک کامل t.me"""
    raw = raw_input.strip()
    # اگر لینک t.me داده شده بود
    match = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_]+)", raw)
    if match:
        return match.group(1).lower()
    # حذف @ اولیه
    raw = re.sub(r"^@", "", raw)
    # فقط کاراکترهای مجاز شناسه تلگرام
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "", raw)
    return cleaned.lower()


def verify_and_add_channel(channel_id, config_path="config/channels.json"):
    channel_id = clean_channel_id(channel_id)
    if not channel_id or len(channel_id) < 4:
        logger.error(f"شناسه کانال نامعتبر است: {channel_id}")
        return False, "شناسه کانال نامعتبر است (حداقل ۴ کاراکتر)."

    # خواندن کانفیگ فعلی
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    channels = config.get("channels", [])

    # بررسی آیا از قبل موجود است
    for ch in channels:
        if ch["id"].lower() == channel_id:
            logger.info(f"کانال {channel_id} از قبل در لیست وجود دارد.")
            return True, f"کانال '{channel_id}' از قبل در لیست موجود است."

    # بررسی در دسترس بودن و عمومی بودن کانال در تلگرام
    url = f"https://t.me/s/{channel_id}"
    logger.info(f"در حال بررسی صحت کانال در تلگرام: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            return False, f"کانال '{channel_id}' در تلگرام یافت نشد (404)."

        parsed = parse_channel_page(resp.text, channel_id)
        if parsed.get("status") != "ok":
            return False, f"کانال '{channel_id}' عمومی نیست یا اجازه پیش‌نمایش وب نمی‌دهد."

        channel_meta = parsed["channel"]
        channel_title = channel_meta.get("title") or channel_id
        channel_desc = channel_meta.get("description") or ""

        # افزودن به لیست کانال‌ها
        new_channel_entry = {
            "id": channel_id,
            "title": channel_title,
            "enabled": True,
            "description": channel_desc[:120]
        }
        channels.append(new_channel_entry)
        config["channels"] = channels

        # ذخیره فایل کانفیگ بروز شده
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ کانال '{channel_title}' ({channel_id}) با موفقیت به کانفیگ اضافه شد.")

        # استخراج فوری داده‌های همین کانال
        run_collector(config_path=config_path, single_channel=channel_id)
        return True, f"کانال '{channel_title}' با موفقیت اضافه و پست‌های آن دریافت شد."

    except Exception as e:
        logger.exception(f"خطا در بررسی کانال: {e}")
        return False, f"خطای سیستمی در ارتباط با تلگرام: {str(e)}"


def add_channels_bulk(channel_inputs, config_path="config/channels.json"):
    """پشتیبانی از افزودن یک یا چند کانال تلگرام به صورت همزمان (تکی یا گروهی)."""
    raw_list = re.split(r"[,;\s\n\r]+", channel_inputs.strip())
    cleaned_ids = []
    for raw in raw_list:
        cid = clean_channel_id(raw)
        if cid and len(cid) >= 4 and cid not in cleaned_ids:
            cleaned_ids.append(cid)

    if not cleaned_ids:
        return False, "شناسه کانال نامعتبر است (حداقل ۴ کاراکتر)."

    results = []
    overall_success = False
    for cid in cleaned_ids:
        ok, msg = verify_and_add_channel(cid, config_path=config_path)
        if ok:
            overall_success = True
        results.append(f"@{cid}: {msg}")

    return overall_success, "\n".join(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="افزودن کانال تلگرام به Bale Telegram Viewer")
    parser.add_argument("--channel", required=True, help="شناسه یک یا چند کانال تلگرام (مثال: isna یا @isna,zoomit)")
    parser.add_argument("--config", default="config/channels.json", help="مسیر فایل کانفیگ")
    args = parser.parse_args()

    # ریشه پروژه
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)

    success, msg = add_channels_bulk(args.channel, config_path=args.config)
    print(msg)
    sys.exit(0 if success else 1)
