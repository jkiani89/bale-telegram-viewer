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


def download_media_file(url, output_path, max_size_mb=12, session=None):
    """
    دانلود فایل‌های صوتی یا ویدیویی با بررسی سقف حجم مجاز (Streaming).
    اگر حجم فایل بیش از سقف تعیین‌شده باشد، دانلود نمی‌شود تا حجم مخزن کنترل شود.
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        http = session or requests
        max_bytes = int(max_size_mb * 1024 * 1024)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://t.me/"
        }

        # ارسال درخواست با استریم
        with http.get(url, headers=headers, stream=True, timeout=20) as resp:
            if resp.status_code != 200:
                logger.warning(f"خطای HTTP {resp.status_code} در دانلود مدیا: {url}")
                return False

            # بررسی Content-Length
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                logger.info(f"فایل مدیا با حجم {int(content_length) // (1024 * 1024)}MB از سقف {max_size_mb}MB بیشتر است؛ رد شد.")
                return False

            downloaded_bytes = 0
            temp_path = output_path + ".tmp"

            with open(temp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > max_bytes:
                            logger.info(f"حجم استریم از {max_size_mb}MB عبور کرد؛ توقف دانلود.")
                            f.close()
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            return False
                        f.write(chunk)

            os.replace(temp_path, output_path)
            size_kb = os.path.getsize(output_path) // 1024
            logger.info(f"مدیا با موفقیت ذخیره شد ({size_kb} KB): {output_path}")
            return True

    except Exception as e:
        logger.warning(f"خطا در دانلود مدیا {url}: {e}")
        return False


def cleanup_orphaned_media(channel_id, active_local_paths, base_media_dir="media"):
    """
    حذف فایل‌های تصویری، صوتی و ویدیویی که دیگر در پیام‌های پنجره لغزان فعال حضور ندارند.
    این تابع تضمین می‌کند که مخزن هرگز با مدیاهای قدیمی پر نشود.
    """
    channel_dir = os.path.join(base_media_dir, channel_id)
    if not os.path.isdir(channel_dir):
        return

    normalized_active = {os.path.abspath(p) for p in active_local_paths}

    media_extensions = (".webp", ".mp4", ".mp3", ".ogg")
    deleted_count = 0
    for root, _, files in os.walk(channel_dir):
        for f in files:
            if f.endswith(media_extensions):
                full_path = os.path.abspath(os.path.join(root, f))
                if full_path not in normalized_active:
                    try:
                        os.remove(full_path)
                        deleted_count += 1
                    except OSError as e:
                        logger.warning(f"خطا در حذف مدیای اضافه {full_path}: {e}")

    if deleted_count > 0:
        logger.info(f"تعداد {deleted_count} فایل مدیای منقضی‌شده از کانال {channel_id} پاکسازی شد.")
