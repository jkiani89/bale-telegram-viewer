"""
اسکریپت اصلی جمع‌آوری داده‌ها (Collector Entry Point).
اجراکننده چرخه اسکرپ، فیلتر لغزان، پردازش مدیا و تولید خروجی JSON.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import requests

from parser import parse_channel_page
from media import download_and_optimize_image, download_media_file, cleanup_orphaned_media

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Collector")


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_channel_html(channel_id, base_url, session):
    url = f"{base_url.rstrip('/')}/{channel_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    logger.info(f"در حال دریافت صفحه: {url}")
    resp = session.get(url, headers=headers, timeout=20)
    if resp.status_code == 200:
        return resp.text
    elif resp.status_code == 404:
        logger.error(f"کانال پیدا نشد (404): {channel_id}")
        return None
    elif resp.status_code == 429:
        logger.warning(f"محدودیت نرخ تلگرام (429) روی کانال: {channel_id}")
        return None
    else:
        logger.error(f"خطای HTTP {resp.status_code} برای کانال {channel_id}")
        return None


def run_collector(config_path="config/channels.json", data_dir="data", media_dir="media", single_channel=None):
    config = load_config(config_path)
    settings = config.get("settings", {})
    channels = config.get("channels", [])

    max_posts = settings.get("max_posts_per_channel", 50)
    max_age_days = settings.get("max_age_days", 7)
    request_delay = settings.get("request_delay_seconds", 2.5)
    base_url = settings.get("telegram_base_url", "https://t.me/s")
    img_conf = settings.get("image_compression", {})
    max_img_width = img_conf.get("max_width", 1080)
    img_quality = img_conf.get("quality", 75)

    media_limits = settings.get("media_limits", {})
    download_videos = media_limits.get("download_short_videos", True)
    max_video_size_mb = media_limits.get("max_video_size_mb", 12)
    download_audios = media_limits.get("download_audio", True)
    max_audio_size_mb = media_limits.get("max_audio_size_mb", 15)

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(media_dir, exist_ok=True)

    session = requests.Session()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    min_timestamp = now_ts - (max_age_days * 86400)

    index_channels = []

    for idx, ch in enumerate(channels):
        channel_id = ch["id"]
        if single_channel and channel_id != single_channel:
            continue

        if not ch.get("enabled", True):
            logger.info(f"کانال {channel_id} غیرفعال است؛ نادیده گرفته شد.")
            continue

        # تاخیر مودبانه بین درخواست‌ها
        if idx > 0 and request_delay > 0:
            jitter = random.uniform(request_delay * 0.8, request_delay * 1.3)
            time.sleep(jitter)

        try:
            html = fetch_channel_html(channel_id, base_url, session)
            if not html:
                continue

            parsed = parse_channel_page(html, channel_id)
            if parsed.get("status") != "ok":
                logger.warning(f"عدم دریافت پست‌ها از {channel_id}: {parsed.get('error')}")
                continue

            channel_meta = parsed["channel"]
            raw_messages = parsed["messages"]

            # اعمال فیلتر پنجره لغزان (تعداد و سن پست)
            # برای جلوگیری از خالی ماندن کانال‌های کم‌پست، همواره حداقل ۱۵ پیام اخیر (یا کل پیام‌های موجود) حفظ می‌شوند
            recent_by_date = [m for m in raw_messages if m["timestamp"] >= min_timestamp]
            if len(recent_by_date) >= 15:
                filtered_messages = recent_by_date
            else:
                # اگر پیام‌های ۷ روز اخیر کمتر از ۱۵ تا بود، ۱۵ پیام آخر در دسترس را نگه می‌داریم
                filtered_messages = raw_messages[-min(len(raw_messages), 20):]

            # اعمال سقف نهایی تعداد پیام‌ها
            if len(filtered_messages) > max_posts:
                filtered_messages = filtered_messages[-max_posts:]

            logger.info(f"کانال {channel_id}: {len(filtered_messages)} پیام استخراج شد.")

            # ردگیری فایل‌های تصویری که باید نگه داشته شوند
            active_media_files = set()

            # ۱. دانلود آواتار کانال
            if channel_meta.get("avatar_remote_url"):
                avatar_path = os.path.join(media_dir, channel_id, "avatar.webp")
                if download_and_optimize_image(
                    channel_meta["avatar_remote_url"],
                    avatar_path,
                    max_width=320,
                    quality=80,
                    session=session
                ):
                    active_media_files.add(avatar_path)
                    channel_meta["avatar"] = f"media/{channel_id}/avatar.webp"
                else:
                    channel_meta["avatar"] = None
            else:
                channel_meta["avatar"] = None

            # ۲. دانلود عکس‌های پست‌ها و تامبنیل ویدیوها
            for msg in filtered_messages:
                # عکس‌ها
                for p in msg.get("_remote_photos", []):
                    rel_path = p["local_rel_path"]
                    full_path = os.path.join(os.getcwd(), rel_path)
                    if download_and_optimize_image(
                        p["remote_url"],
                        full_path,
                        max_width=max_img_width,
                        quality=img_quality,
                        session=session
                    ):
                        active_media_files.add(full_path)

                # تامبنیل ویدیو و خود فایل ویدیو
                v_info = msg.get("_video_info")
                if v_info:
                    if v_info.get("remote_thumb_url"):
                        thumb_rel_path = v_info["local_thumb_path"]
                        thumb_full_path = os.path.join(os.getcwd(), thumb_rel_path)
                        if download_and_optimize_image(
                            v_info["remote_thumb_url"],
                            thumb_full_path,
                            max_width=max_img_width,
                            quality=img_quality,
                            session=session
                        ):
                            active_media_files.add(thumb_full_path)

                    # دانلود ویدیوی کوتاه در صورت وجود
                    if download_videos and v_info.get("remote_video_url"):
                        video_rel_path = v_info["local_video_path"]
                        video_full_path = os.path.join(os.getcwd(), video_rel_path)
                        if download_media_file(
                            v_info["remote_video_url"],
                            video_full_path,
                            max_size_mb=max_video_size_mb,
                            session=session
                        ):
                            active_media_files.add(video_full_path)
                            msg["media"]["video"]["local_video_url"] = video_rel_path

                # صوت و ویس (Voice & Audio)
                a_info = msg.get("_audio_info")
                if a_info and download_audios and a_info.get("remote_audio_url"):
                    audio_rel_path = a_info["local_audio_path"]
                    audio_full_path = os.path.join(os.getcwd(), audio_rel_path)
                    if download_media_file(
                        a_info["remote_audio_url"],
                        audio_full_path,
                        max_size_mb=max_audio_size_mb,
                        session=session
                    ):
                        active_media_files.add(audio_full_path)
                        msg["media"]["audio"]["local_audio_url"] = audio_rel_path

            # ۳. پاکسازی مدیاهای منقضی‌شده کانال
            cleanup_orphaned_media(channel_id, active_media_files, base_media_dir=media_dir)

            # ۴. تمیزسازی فیلدهای موقت پیام‌ها قبل از ذخیره JSON
            clean_messages = []
            for msg in filtered_messages:
                m_copy = dict(msg)
                m_copy.pop("_remote_photos", None)
                m_copy.pop("_video_info", None)
                m_copy.pop("_audio_info", None)
                clean_messages.append(m_copy)

            # ۵. ذخیره فایل فید کانال: data/<channel_id>.json
            feed_data = {
                "channel": channel_meta,
                "messages": clean_messages
            }
            channel_file = os.path.join(data_dir, f"{channel_id}.json")
            with open(channel_file, "w", encoding="utf-8") as f:
                json.dump(feed_data, f, ensure_ascii=False, indent=2)

            # ۶. آماده‌سازی ورودی این کانال برای index.json
            last_msg = clean_messages[-1] if clean_messages else None
            snippet = ""
            if last_msg:
                # حذف تگ‌ها برای snippet خلاصه
                raw_text = last_msg["text_html"].replace("<br>", " ")
                clean_text = "".join(BeautifulSoup(raw_text, "html.parser").strings).strip()
                snippet = clean_text[:90] + ("..." if len(clean_text) > 90 else "")

            index_channels.append({
                "id": channel_id,
                "title": ch.get("title") or channel_meta["title"],
                "avatar": channel_meta["avatar"],
                "description": ch.get("description") or channel_meta["description"],
                "last_post": {
                    "id": last_msg["id"] if last_msg else None,
                    "date": last_msg["date"] if last_msg else None,
                    "timestamp": last_msg["timestamp"] if last_msg else None,
                    "snippet": snippet
                } if last_msg else None,
                "total_posts": len(clean_messages)
            })

        except Exception as e:
            logger.exception(f"خطای غیرمنتظره در پردازش کانال {channel_id}: {e}")

    # ۷. ذخیره فایل منیفست کلی: data/index.json
    index_manifest = {
        "updated_at": now_ts,
        "channels": index_channels
    }
    index_file = os.path.join(data_dir, "index.json")
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, ensure_ascii=False, indent=2)

    logger.info(f"عملیات با موفقیت پایان یافت. {len(index_channels)} کانال در {index_file} ذخیره شد.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram Public Channel Collector")
    parser.add_argument("--config", default="config/channels.json", help="مسیر فایل تنظیمات کانال‌ها")
    parser.add_argument("--data-dir", default="data", help="مسیر ذخیره فایل‌های JSON")
    parser.add_argument("--media-dir", default="media", help="مسیر ذخیره عکس‌های WebP")
    parser.add_argument("--channel", default=None, help="شناسه کانال خاص برای تست تک‌کاناله")
    args = parser.parse_args()

    # تنظیم دایرکتوری جاری به ریشه پروژه
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)

    run_collector(
        config_path=args.config,
        data_dir=args.data_dir,
        media_dir=args.media_dir,
        single_channel=args.channel
    )
