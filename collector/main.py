"""
اسکریپت اصلی جمع‌آوری داده‌ها (Collector Entry Point).
اجراکننده چرخه اسکرپ، ادغام مقاوم، فیلتر لغزان، پردازش مدیا و تولید خروجی JSON.
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

# اطمینان از قرار داشتن مسیر collector در sys.path چه به صورت ماژول و چه مستقیم
collector_dir = os.path.dirname(os.path.abspath(__file__))
if collector_dir not in sys.path:
    sys.path.insert(0, collector_dir)

try:
    from parser import parse_channel_page
    from media import download_and_optimize_image, download_media_file, cleanup_orphaned_media
except ImportError:
    from collector.parser import parse_channel_page
    from collector.media import download_and_optimize_image, download_media_file, cleanup_orphaned_media

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Collector")


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_manifest(index_file):
    """بارگذاری منیفست index.json موجود جهت حفظ لیست کانال‌ها در صورت خطای موقت."""
    if not os.path.exists(index_file):
        return {}
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                c["id"]: c
                for c in data.get("channels", [])
                if isinstance(c, dict) and "id" in c
            }
    except Exception as e:
        logger.warning(f"عدم امکان خواندن index.json قبلی: {e}")
        return {}


def load_existing_feed(feed_file):
    """بارگذاری فید ذخیره‌شده قبلی کانال جهت ادغام پست‌ها."""
    if not os.path.exists(feed_file):
        return None
    try:
        with open(feed_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"عدم امکان خواندن فید موجود {feed_file}: {e}")
        return None


def extract_snippet_from_messages(clean_messages):
    """تولید چکیده متن آخرین پست برای کارت کانال."""
    if not clean_messages:
        return None, None, None, ""
    last_msg = clean_messages[-1]
    raw_text = last_msg.get("text_html", "").replace("<br>", " ")
    clean_text = "".join(BeautifulSoup(raw_text, "html.parser").strings).strip()
    snippet = clean_text[:90] + ("..." if len(clean_text) > 90 else "")
    return last_msg.get("id"), last_msg.get("date"), last_msg.get("timestamp"), snippet


def build_fallback_entry(channel_id, ch_config, data_dir, existing_index_map):
    """
    تولید مدخل کانال در صورت بروز خطای موقت (429، تایم‌اوت، فیلتر) یا در حالت تک‌کاناله.
    تضمین می‌کند هیچ کانالی از index.json حذف نشود و صفحه کانال 404 ندهد.
    """
    feed_file = os.path.join(data_dir, f"{channel_id}.json")
    existing_feed = load_existing_feed(feed_file)

    # اولویت ۱: اگر در index.json قبلی ثبت شده بود
    if channel_id in existing_index_map:
        entry = dict(existing_index_map[channel_id])
        # اگر فایل فید به هر دلیل در دیسک نبود، یک فایل فید خالی می‌سازیم
        if not existing_feed:
            stub = {
                "channel": {
                    "id": channel_id,
                    "title": entry.get("title") or ch_config.get("title") or channel_id,
                    "description": entry.get("description") or ch_config.get("description") or "",
                    "avatar": entry.get("avatar")
                },
                "messages": []
            }
            try:
                with open(feed_file, "w", encoding="utf-8") as f:
                    json.dump(stub, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return entry

    # اولویت ۲: اگر فایل فید data/<channel>.json از قبل وجود داشت
    if existing_feed and isinstance(existing_feed, dict):
        c_meta = existing_feed.get("channel", {})
        msgs = existing_feed.get("messages", [])
        m_id, m_date, m_ts, snippet = extract_snippet_from_messages(msgs)
        return {
            "id": channel_id,
            "title": ch_config.get("title") or c_meta.get("title") or channel_id,
            "avatar": c_meta.get("avatar"),
            "description": ch_config.get("description") or c_meta.get("description") or "",
            "last_post": {
                "id": m_id,
                "date": m_date,
                "timestamp": m_ts,
                "snippet": snippet
            } if m_id else None,
            "total_posts": len(msgs)
        }

    # اولویت ۳: کانال جدیدی که در اولین تلاش خطا داده است
    placeholder_title = ch_config.get("title") or channel_id
    placeholder_desc = ch_config.get("description") or ""
    stub = {
        "channel": {
            "id": channel_id,
            "title": placeholder_title,
            "description": placeholder_desc,
            "avatar": None
        },
        "messages": []
    }
    try:
        with open(feed_file, "w", encoding="utf-8") as f:
            json.dump(stub, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {
        "id": channel_id,
        "title": placeholder_title,
        "avatar": None,
        "description": placeholder_desc,
        "last_post": None,
        "total_posts": 0
    }


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
    try:
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
    except Exception as e:
        logger.error(f"خطای شبکه در دریافت کانال {channel_id}: {e}")
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
    max_audio_size_mb = media_limits.get("max_audio_size_mb", 25)

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(media_dir, exist_ok=True)

    session = requests.Session()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    min_timestamp = now_ts - (max_age_days * 86400)

    # ۱. بارگذاری منیفست قبلی جهت ادغام هوشمند
    index_file = os.path.join(data_dir, "index.json")
    existing_index_map = load_existing_manifest(index_file)

    index_channels = []

    for idx, ch in enumerate(channels):
        channel_id = ch["id"]

        if not ch.get("enabled", True):
            logger.info(f"کانال {channel_id} غیرفعال است؛ نادیده گرفته شد.")
            continue

        # اگر در حالت تک‌کاناله هستیم و این کانال هدف نیست، نسخه قبلی را حفظ می‌کنیم
        if single_channel and channel_id != single_channel:
            entry = build_fallback_entry(channel_id, ch, data_dir, existing_index_map)
            index_channels.append(entry)
            continue

        # تاخیر مودبانه بین درخواست‌ها
        if idx > 0 and request_delay > 0:
            jitter = random.uniform(request_delay * 0.8, request_delay * 1.3)
            time.sleep(jitter)

        channel_file = os.path.join(data_dir, f"{channel_id}.json")

        try:
            html = fetch_channel_html(channel_id, base_url, session)
            if not html:
                logger.warning(f"عدم دریافت HTML کانال {channel_id}؛ بازیابی از نسخه قبلی...")
                fallback_entry = build_fallback_entry(channel_id, ch, data_dir, existing_index_map)
                index_channels.append(fallback_entry)
                continue

            parsed = parse_channel_page(html, channel_id)
            if parsed.get("status") != "ok":
                logger.warning(f"خطای پارس کانال {channel_id}: {parsed.get('error')}؛ بازیابی نسخه قبلی...")
                fallback_entry = build_fallback_entry(channel_id, ch, data_dir, existing_index_map)
                index_channels.append(fallback_entry)
                continue

            channel_meta = parsed["channel"]
            raw_messages = parsed["messages"]

            # ۲. ادغام پیام‌های قبلی با پیام‌های تازه‌دریافت‌شده
            existing_feed = load_existing_feed(channel_file)
            existing_messages = existing_feed.get("messages", []) if existing_feed else []

            messages_by_id = {}
            for m in existing_messages:
                if isinstance(m, dict) and "id" in m:
                    messages_by_id[m["id"]] = m

            for m in raw_messages:
                if isinstance(m, dict) and "id" in m:
                    # پیام‌های جدیدتر جایگزین نسخه قبلی می‌شوند
                    messages_by_id[m["id"]] = m

            merged_messages = sorted(
                messages_by_id.values(),
                key=lambda x: (x.get("timestamp") or 0, x.get("id") or 0)
            )

            # ۳. اعمال فیلتر پنجره لغزان (تعداد و سن پست)
            recent_by_date = [m for m in merged_messages if (m.get("timestamp") or 0) >= min_timestamp]
            if len(recent_by_date) >= 15:
                filtered_messages = recent_by_date
            else:
                filtered_messages = merged_messages[-min(len(merged_messages), 20):]

            if len(filtered_messages) > max_posts:
                filtered_messages = filtered_messages[-max_posts:]

            logger.info(f"کانال {channel_id}: {len(filtered_messages)} پیام در پنجره فعال تثبیت شد.")

            # ۴. پردازش و دانلود فایل‌های چندرسانه‌ای
            active_media_files = set()

            # آواتار کانال
            if channel_meta.get("avatar_remote_url"):
                avatar_path = os.path.join(media_dir, channel_id, "avatar.webp")
                if download_and_optimize_image(
                    channel_meta["avatar_remote_url"],
                    avatar_path,
                    max_width=320,
                    quality=80,
                    session=session
                ):
                    active_media_files.add(os.path.abspath(avatar_path))
                    channel_meta["avatar"] = f"media/{channel_id}/avatar.webp"
                else:
                    # اگر دانلود نشد و نسخه قبلی وجود دارد حفظ شود
                    if os.path.exists(avatar_path):
                        active_media_files.add(os.path.abspath(avatar_path))
                        channel_meta["avatar"] = f"media/{channel_id}/avatar.webp"
                    else:
                        channel_meta["avatar"] = None
            else:
                channel_meta["avatar"] = None

            # مدیاهای هر پیام
            for msg in filtered_messages:
                # ثبت فایل‌های مدیای پیام‌های قبلی که از قبل دانلود شده‌اند
                media_dict = msg.get("media") or {}
                for p in (media_dict.get("photos") or []):
                    if isinstance(p, dict) and p.get("local_url"):
                        active_media_files.add(os.path.abspath(p["local_url"]))

                v_existing = media_dict.get("video") or {}
                if isinstance(v_existing, dict):
                    if v_existing.get("thumb_url"):
                        active_media_files.add(os.path.abspath(v_existing["thumb_url"]))
                    if v_existing.get("local_video_url"):
                        active_media_files.add(os.path.abspath(v_existing["local_video_url"]))

                a_existing = media_dict.get("audio") or {}
                if isinstance(a_existing, dict) and a_existing.get("local_audio_url"):
                    active_media_files.add(os.path.abspath(a_existing["local_audio_url"]))

                # دانلود عکس‌های پیام جدید
                for p in msg.get("_remote_photos", []):
                    rel_path = p["local_rel_path"]
                    full_path = os.path.abspath(rel_path)
                    if download_and_optimize_image(
                        p["remote_url"],
                        full_path,
                        max_width=max_img_width,
                        quality=img_quality,
                        session=session
                    ):
                        active_media_files.add(full_path)

                # تامبنیل و ویدیوی پیام جدید
                v_info = msg.get("_video_info")
                if v_info:
                    if v_info.get("remote_thumb_url"):
                        thumb_rel_path = v_info["local_thumb_path"]
                        thumb_full_path = os.path.abspath(thumb_rel_path)
                        if download_and_optimize_image(
                            v_info["remote_thumb_url"],
                            thumb_full_path,
                            max_width=max_img_width,
                            quality=img_quality,
                            session=session
                        ):
                            active_media_files.add(thumb_full_path)
                        else:
                            v_info["thumb_url"] = None

                    if download_videos and v_info.get("remote_video_url"):
                        video_rel_path = v_info["local_video_path"]
                        video_full_path = os.path.abspath(video_rel_path)
                        if download_media_file(
                            v_info["remote_video_url"],
                            video_full_path,
                            max_size_mb=max_video_size_mb,
                            session=session
                        ):
                            active_media_files.add(video_full_path)
                            msg.setdefault("media", {}).setdefault("video", {})["local_video_url"] = video_rel_path

                # صوت و ویس پیام جدید
                a_info = msg.get("_audio_info")
                if a_info and download_audios and a_info.get("remote_audio_url"):
                    audio_rel_path = a_info["local_audio_path"]
                    audio_full_path = os.path.abspath(audio_rel_path)
                    if download_media_file(
                        a_info["remote_audio_url"],
                        audio_full_path,
                        max_size_mb=max_audio_size_mb,
                        session=session
                    ):
                        active_media_files.add(audio_full_path)
                        msg.setdefault("media", {}).setdefault("audio", {})["local_audio_url"] = audio_rel_path

            # ۵. پاکسازی مدیاهای منقضی‌شده
            cleanup_orphaned_media(channel_id, active_media_files, base_media_dir=media_dir)

            # ۶. تمیزسازی فیلدهای موقت پیام‌ها قبل از ذخیره JSON
            clean_messages = []
            for msg in filtered_messages:
                m_copy = dict(msg)
                m_copy.pop("_remote_photos", None)
                m_copy.pop("_video_info", None)
                m_copy.pop("_audio_info", None)
                clean_messages.append(m_copy)

            # ۷. ذخیره فایل فید کانال: data/<channel_id>.json
            feed_data = {
                "channel": channel_meta,
                "messages": clean_messages
            }
            with open(channel_file, "w", encoding="utf-8") as f:
                json.dump(feed_data, f, ensure_ascii=False, indent=2)

            # ۸. ساخت ورودی منیفست
            m_id, m_date, m_ts, snippet = extract_snippet_from_messages(clean_messages)

            index_channels.append({
                "id": channel_id,
                "title": ch.get("title") or channel_meta.get("title") or channel_id,
                "avatar": channel_meta.get("avatar"),
                "description": ch.get("description") or channel_meta.get("description") or "",
                "last_post": {
                    "id": m_id,
                    "date": m_date,
                    "timestamp": m_ts,
                    "snippet": snippet
                } if m_id else None,
                "total_posts": len(clean_messages)
            })

        except Exception as e:
            logger.exception(f"خطای غیرمنتظره در پردازش کانال {channel_id}: {e}؛ بازیابی نسخه قبلی...")
            fallback_entry = build_fallback_entry(channel_id, ch, data_dir, existing_index_map)
            index_channels.append(fallback_entry)

    # ۹. ذخیره فایل منیفست کلی: data/index.json
    index_manifest = {
        "updated_at": now_ts,
        "channels": index_channels
    }
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, ensure_ascii=False, indent=2)

    logger.info(f"عملیات با موفقیت پایان یافت. {len(index_channels)} کانال در {index_file} تثبیت شد.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram Public Channel Collector")
    parser.add_argument("--config", default="config/channels.json", help="مسیر فایل تنظیمات کانال‌ها")
    parser.add_argument("--data-dir", default="data", help="مسیر ذخیره فایل‌های JSON")
    parser.add_argument("--media-dir", default="media", help="مسیر ذخیره عکس‌های WebP")
    parser.add_argument("--channel", default=None, help="شناسه کانال خاص برای تست تک‌کاناله")
    args = parser.parse_args()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)

    run_collector(
        config_path=args.config,
        data_dir=args.data_dir,
        media_dir=args.media_dir,
        single_channel=args.channel
    )
