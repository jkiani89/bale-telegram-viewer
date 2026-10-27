"""
ماژول دانلود، بهینه‌سازی، تبدیل به WebP و پاکسازی رسانه‌های منقضی‌شده.
"""

import io
import os
import logging
from PIL import Image
import requests

logger = logging.getLogger(__name__)


def download_and_optimize_image(url, output_path, max_width=1080, quality=75, session=None):
    """
    دانلود تصویر از آدرس تلگرام، تغییر اندازه (در صورت نیاز)، و فشرده‌سازی در فرمت WebP.
    اگر فایل از قبل با اندازه معقول وجود داشته باشد، مجدداً دانلود نمی‌شود (کش محلی).
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        http = session or requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://t.me/"
        }

        resp = http.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"خطا در دانلود عکس ({resp.status_code}): {url}")
            return False

        # باز کردن تصویر با Pillow
        img = Image.open(io.BytesIO(resp.content))

        # تبدیل به حالت RGB (در صورت RGBA یا پلت رنگی)
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            # اگر آلفا دارد، تبدیل با زمینه سفید
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert("RGB")

        # تغییر اندازه در صورت بزرگتر بودن از سقف عرض
        if img.width > max_width:
            new_height = int((max_width / img.width) * img.height)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # ذخیره نهایی با فرمت WebP
        img.save(output_path, "WEBP", quality=quality, method=6)
        logger.info(f"تصویر ذخیره شد ({os.path.getsize(output_path) // 1024} KB): {output_path}")
        return True

    except Exception as e:
        logger.error(f"خطای پردازش تصویر {url}: {e}")
        return False


def cleanup_orphaned_media(channel_id, active_local_paths, base_media_dir="media"):
    """
    حذف فایل‌های تصویری که دیگر در پیام‌های پنجره لغزان فعال حضور ندارند.
    این تابع تضمین می‌کند که مخزن هرگز با عکس‌های قدیمی پر نشود.
    """
    channel_dir = os.path.join(base_media_dir, channel_id)
    if not os.path.isdir(channel_dir):
        return

    # نرمال‌سازی مسیرهای فعال برای مقایسه دقیق
    normalized_active = {os.path.abspath(p) for p in active_local_paths}

    deleted_count = 0
    for root, _, files in os.walk(channel_dir):
        for f in files:
            if f.endswith(".webp"):
                full_path = os.path.abspath(os.path.join(root, f))
                if full_path not in normalized_active:
                    try:
                        os.remove(full_path)
                        deleted_count += 1
                    except OSError as e:
                        logger.warning(f"خطا در حذف عکس اضافه {full_path}: {e}")

    if deleted_count > 0:
        logger.info(f"تعداد {deleted_count} تصویر منقضی‌شده از کانال {channel_id} پاکسازی شد.")
