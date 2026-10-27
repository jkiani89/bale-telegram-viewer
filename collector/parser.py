"""
ماژول پارس ساختار HTML صفحات عمومی تلگرام (t.me/s/<channel>)
مقاوم در برابر تغییرات جزئی ساختار و استخراج‌کننده متادیتا، پیام‌ها، و رسانه‌ها.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString, Tag

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "strike", "code", "pre", "a", "br"}


def clean_html_formatting(soup_element):
    """
    پاکسازی و بهینه‌سازی تگ‌های HTML متن پیام تلگرام.
    حفظ ساختار فرمت‌بندی (بولد، ایتالیک، لینک، کد) و حذف اسکریپت‌ها یا استایل‌های ناامن.
    """
    if not soup_element:
        return ""

    def process_node(node):
        if isinstance(node, NavigableString):
            # تبدیل کاراکترهای خاص HTML
            text = str(node)
            return (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

        if not isinstance(node, Tag):
            return ""

        tag_name = node.name.lower()

        if tag_name == "br":
            return "<br>"

        # بازگشتی برای فرزندان
        children_html = "".join(process_node(child) for child in node.children)

        if tag_name in {"b", "strong"}:
            return f"<b>{children_html}</b>"
        elif tag_name in {"i", "em"}:
            return f"<i>{children_html}</i>"
        elif tag_name in {"u"}:
            return f"<u>{children_html}</u>"
        elif tag_name in {"s", "strike"}:
            return f"<s>{children_html}</s>"
        elif tag_name == "code":
            return f"<code>{children_html}</code>"
        elif tag_name == "pre":
            return f"<pre>{children_html}</pre>"
        elif tag_name == "a":
            href = node.get("href", "")
            # جلوگیری از لینک‌های جاوااسکریپت و ناامن
            if href.startswith(("http://", "https://", "tg://")):
                return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{children_html}</a>'
            return children_html

        # سایر تگ‌های متفرقه تلگرام (مثل spanهای ایموجی یا فرمت)
        return children_html

    result = "".join(process_node(child) for child in soup_element.children)
    # اصلاح فاصله‌ها و شکست‌های خطی متوالی زائد
    result = re.sub(r"(<br>\s*){3,}", "<br><br>", result.strip())
    return result


def extract_background_image_url(style_attr):
    """استخراج آدرس تصویر از ویژگی style='background-image:url(...)'"""
    if not style_attr:
        return None
    match = re.search(r"background-image\s*:\s*url\s*\(\s*['\"]?(.*?)['\"]?\s*\)", style_attr, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_channel_page(html_content, channel_id):
    """
    پارس کامل صفحه t.me/s/<channel_id>.
    خروجی: دیکشنری حاوی متادیتای کانال و لیست پیام‌ها
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # بررسی محدودیت یا مسدود بودن پیش‌نمایش کانال
    error_wrap = soup.select_one(".tgme_page_error, .tgme_channel_info_error")
    page_title = soup.title.string if soup.title else ""
    if (error_wrap and "can't be displayed" in error_wrap.get_text()) or "Contact @" in page_title:
        return {
            "status": "restricted",
            "error": "این شناسه یک کانال عمومی دارای پیش‌نمایش وب نیست (ممکن است حساب کاربری یا گروه خصوصی باشد).",
            "channel": None,
            "messages": []
        }

    # استخراج اطلاعات متادیتای کانال
    title_el = soup.select_one(".tgme_channel_info_header_title, .tgme_page_title")
    title = title_el.get_text(strip=True) if title_el else channel_id

    desc_el = soup.select_one(".tgme_channel_info_description, .tgme_page_description")
    description = desc_el.get_text(strip=True) if desc_el else ""

    avatar_el = soup.select_one(".tgme_page_photo_image img, .tgme_channel_info_header_avatar img")
    avatar_url = avatar_el.get("src") if avatar_el else None

    subscribers_el = soup.select_one(".tgme_channel_info_counter .counter_value")
    subscribers = subscribers_el.get_text(strip=True) if subscribers_el else None

    verified = bool(soup.select_one(".verified-icon"))

    channel_meta = {
        "id": channel_id,
        "title": title,
        "description": description,
        "avatar_remote_url": avatar_url,
        "avatar": f"media/{channel_id}/avatar.webp" if avatar_url else None,
        "subscribers": subscribers,
        "verified": verified,
        "last_updated": int(datetime.now(timezone.utc).timestamp())
    }

    # استخراج لیست پیام‌ها
    messages = []
    message_wraps = soup.select(".tgme_widget_message_wrap")

    for wrap in message_wraps:
        msg_el = wrap.select_one(".tgme_widget_message")
        if not msg_el:
            continue

        # شناسه پست: data-post="channel_id/531"
        data_post = msg_el.get("data-post", "")
        post_id = None
        if "/" in data_post:
            try:
                post_id = int(data_post.split("/")[-1])
            except ValueError:
                pass

        if not post_id:
            continue

        # تاریخ و زمان
        time_el = msg_el.select_one(".tgme_widget_message_date time")
        date_iso = time_el.get("datetime") if time_el else None
        timestamp = 0
        if date_iso:
            try:
                # تبدیل ISO 8601 به تایم‌استمپ ثانیه‌ای
                dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                timestamp = int(dt.timestamp())
            except Exception:
                timestamp = int(datetime.now(timezone.utc).timestamp())

        # بازدیدها
        views_el = msg_el.select_one(".tgme_widget_message_views")
        views = views_el.get_text(strip=True) if views_el else None

        # متن پیام
        text_el = msg_el.select_one(".tgme_widget_message_text")
        text_html = clean_html_formatting(text_el) if text_el else ""

        # فوروارد شده از کانال دیگر
        fwd_el = msg_el.select_one(".tgme_widget_message_forwarded_from_name")
        forward_from = fwd_el.get_text(strip=True) if fwd_el else None

        # پاسخ به پیام دیگر (Reply)
        reply_el = msg_el.select_one(".tgme_widget_message_reply")
        reply_to = None
        if reply_el:
            reply_href = reply_el.get("href", "")
            reply_id_match = re.search(r"/(\d+)$", reply_href)
            reply_id = int(reply_id_match.group(1)) if reply_id_match else None
            snippet_el = reply_el.select_one(".tgme_widget_message_metatext, .tgme_widget_message_text")
            reply_snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            reply_to = {
                "id": reply_id,
                "text_snippet": reply_snippet[:100]
            }

        # بررسی رسانه‌ها (عکس و ویدیو)
        media_type = "none"
        remote_photos = []
        video_info = None

        # عکس‌ها
        photo_wraps = msg_el.select(".tgme_widget_message_photo_wrap")
        for idx, pw in enumerate(photo_wraps):
            style = pw.get("style", "")
            bg_url = extract_background_image_url(style)
            if bg_url:
                remote_photos.append({
                    "remote_url": bg_url,
                    "local_rel_path": f"media/{channel_id}/{post_id}_{idx}.webp",
                    "index": idx
                })

        if remote_photos:
            media_type = "photo"

        # ویدیو
        video_el = msg_el.select_one(".tgme_widget_message_video_player, .tgme_widget_message_video, video")
        if video_el:
            media_type = "video"
            duration_el = msg_el.select_one(".message_video_duration, .tgme_widget_message_video_duration")
            duration = duration_el.get_text(strip=True) if duration_el else None

            # استخراج آدرس مستقیم ویدیو (mp4)
            actual_video_tag = video_el if video_el.name == "video" else video_el.select_one("video")
            video_src = actual_video_tag.get("src") if actual_video_tag else None

            # تامبنیل ویدیو
            thumb_url = None
            thumb_wrap = msg_el.select_one(".tgme_widget_message_video_thumb")
            if thumb_wrap:
                thumb_url = extract_background_image_url(thumb_wrap.get("style", ""))

            video_info = {
                "duration": duration,
                "remote_video_url": video_src,
                "local_video_path": f"media/{channel_id}/{post_id}.mp4" if video_src else None,
                "remote_thumb_url": thumb_url,
                "local_thumb_path": f"media/{channel_id}/{post_id}_thumb.webp" if thumb_url else None,
                "original_url": f"https://t.me/{channel_id}/{post_id}"
            }

        # صوت، ویس و اسناد (Audio, Voice & Documents)
        audio_info = None
        document_info = None

        # الف) ویس یا صوت با پلیر وب مستقیم
        audio_el = msg_el.select_one("audio, .tgme_widget_message_voice")
        if audio_el:
            actual_audio_tag = audio_el if audio_el.name == "audio" else audio_el.select_one("audio")
            audio_src = actual_audio_tag.get("src") if actual_audio_tag else None
            dur_el = msg_el.select_one(".tgme_widget_message_voice_duration, .audio_duration")
            audio_duration = dur_el.get_text(strip=True) if dur_el else None
            title_el = msg_el.select_one(".tgme_widget_message_document_title")
            audio_title = title_el.get_text(strip=True) if title_el else "پیام صوتی"

            if audio_src:
                media_type = "audio"
                audio_info = {
                    "title": audio_title,
                    "duration": audio_duration,
                    "remote_audio_url": audio_src,
                    "local_audio_path": f"media/{channel_id}/{post_id}.mp3",
                    "original_url": f"https://t.me/{channel_id}/{post_id}",
                    "is_streamable": True
                }

        # ب) فایل ضمیمه یا موزیک/پادکست (Document Wrap)
        doc_wrap = msg_el.select_one(".tgme_widget_message_document_wrap")
        if doc_wrap:
            doc_icon = doc_wrap.select_one(".tgme_widget_message_document_icon")
            is_audio_doc = bool(doc_icon and "audio" in doc_icon.get("class", []))
            
            title_el = doc_wrap.select_one(".tgme_widget_message_document_title")
            extra_el = doc_wrap.select_one(".tgme_widget_message_document_extra")
            
            doc_title = title_el.get_text(strip=True) if title_el else ("فایل صوتی" if is_audio_doc else "سند ضمیمه")
            doc_extra = extra_el.get_text(strip=True) if extra_el else ""
            doc_url = doc_wrap.get("href") or f"https://t.me/{channel_id}/{post_id}"

            if is_audio_doc:
                if not audio_info:
                    media_type = "audio"
                    audio_info = {
                        "title": doc_title,
                        "duration": doc_extra,
                        "remote_audio_url": None,
                        "local_audio_path": None,
                        "original_url": doc_url,
                        "is_streamable": False
                    }
            else:
                if media_type == "none":
                    media_type = "document"
                document_info = {
                    "title": doc_title,
                    "extra": doc_extra,
                    "original_url": doc_url
                }

        # ایجاد شیء نهایی پیام
        msg_obj = {
            "id": post_id,
            "date": date_iso,
            "timestamp": timestamp,
            "text_html": text_html,
            "views": views,
            "media_type": media_type,
            "media": {
                "photos": [
                    {"url": rp["local_rel_path"], "remote_url": rp["remote_url"]}
                    for rp in remote_photos
                ],
                "video": video_info,
                "audio": audio_info,
                "document": document_info
            },
            "forward_from": forward_from,
            "reply_to": reply_to,
            "original_url": f"https://t.me/{channel_id}/{post_id}",
            "_remote_photos": remote_photos,  # متادیتای داخلی برای دانلود
            "_video_info": video_info,
            "_audio_info": audio_info
        }

        messages.append(msg_obj)

    # مرتب‌سازی پیام‌ها از شناسه کمتر به بیشتر (قدیم به جدید)
    messages.sort(key=lambda m: m["id"])

    return {
        "status": "ok",
        "error": None,
        "channel": channel_meta,
        "messages": messages
    }
