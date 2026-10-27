# مستند مشخصات اسکیما و فرمت‌های داده (JSON Data Schemas)

این سند مشخصات دقیق تمام ساختارهای داده‌ای پروژه **Bale Telegram Viewer** را تعریف می‌کند تا میان جمع‌کننده داده (Collector) و رابط کاربری مینی‌اپ (MiniApp) هماهنگی ۱۰۰٪ برقرار باشد.

---

## ۱. فایل تنظیمات کانال‌ها (`config/channels.json`)

این فایل توسط توسعه‌دهنده ویرایش می‌شود و ورودی اسکریپت Collector است.

### فیلدها:
* `settings`: تنظیمات عمومی جمع‌آوری داده.
  * `max_posts_per_channel` (عدد): حداکثر تعداد پست‌های ذخیره‌شده برای هر کانال (پنجره لغزان).
  * `max_age_days` (عدد): پست‌های قدیمی‌تر از این تعداد روز پاکسازی می‌شوند.
  * `request_delay_seconds` (اعشاری): تاخیر تصادفی بین درخواست‌ها جهت عدم تحریک محدودیت تلگرام.
  * `image_compression`:
    * `format`: فرمت خروجی تصویر (`webp`).
    * `quality`: کیفیت فشرده‌سازی (پیش‌فرض: `75`).
    * `max_width`: حداکثر عرض پیکسل برای عکس‌ها (پیش‌فرض: `1080`).
* `channels`: آرایه‌ای از کانال‌ها:
  * `id` (رشته): نام کاربری عمومی کانال (همان عبارتی که در `t.me/s/<id>` است).
  * `title` (رشته): نام نمایشی کانال در رابط کاربری مینی‌اپ.
  * `enabled` (بولی): آیا این کانال باید در چرخه جمع‌آوری بررسی شود یا خیر.
  * `description` (رشته اختیاری): توضیح کوتاه درباره کانال.

---

## ۲. ایندکس سبک کانال‌ها برای صفحه اصلی مینی‌اپ (`data/index.json`)

این فایل به عنوان منیفست اولیه توسط صفحه اول مینی‌اپ دریافت می‌شود تا لیست کانال‌ها بدون نیاز به دانلود کل پیام‌ها نمایش داده شود.

```json
{
  "updated_at": 1730018400,
  "channels": [
    {
      "id": "durov",
      "title": "Pavel Durov",
      "avatar": "media/durov/avatar.webp",
      "description": "Founder of Telegram",
      "last_post": {
        "id": 531,
        "date": "2026-10-27T08:00:00Z",
        "timestamp": 1730016000,
        "snippet": "We have introduced a major update to Telegram Channels..."
      },
      "total_posts": 45
    }
  ]
}
```

---

## ۳. فید کامل یک کانال (`data/<channel_id>.json`)

این فایل وقتی کاربر روی کانال خاصی کلیک می‌کند توسط مینی‌اپ لود می‌شود.

```json
{
  "channel": {
    "id": "durov",
    "title": "Pavel Durov",
    "avatar": "media/durov/avatar.webp",
    "description": "Founder of Telegram",
    "verified": true,
    "subscribers": "2.8M",
    "last_updated": 1730018400
  },
  "messages": [
    {
      "id": 531,
      "date": "2026-10-27T08:00:00Z",
      "timestamp": 1730016000,
      "text_html": "This is a <b>formatted</b> message with a <a href=\"https://example.com\">link</a>.",
      "views": "1.2M",
      "media_type": "photo",
      "media": {
        "photos": [
          {
            "url": "media/durov/531_0.webp",
            "width": 1080,
            "height": 720
          }
        ],
        "video": null
      },
      "forward_from": null,
      "reply_to": {
        "id": 530,
        "text_snippet": "Previous update announcement..."
      },
      "original_url": "https://t.me/durov/531"
    },
    {
      "id": 532,
      "date": "2026-10-27T09:30:00Z",
      "timestamp": 1730021400,
      "text_html": "Check out this feature preview video!",
      "views": "850K",
      "media_type": "video",
      "media": {
        "photos": [],
        "video": {
          "duration": "01:45",
          "thumb_url": "media/durov/532_thumb.webp",
          "local_video_url": "media/durov/532.mp4",
          "original_url": "https://t.me/durov/532"
        }
      },
      "forward_from": null,
      "reply_to": null,
      "original_url": "https://t.me/durov/532"
    }
  ]
}
```

### انواع رسانه (`media_type`):
1. `none`: پیام متنی ساده بدون هیچ‌گونه فایل رسانه‌ای.
2. `photo`: حاوی یک یا چند عکس که دانلود و به فرمت `webp` فشرده شده‌اند و از مسیر محلی خوانده می‌شوند.
3. `video`: ویدیو. اگر حجم فایل از سقف مجاز کمتر باشد، فایل در `local_video_url` ذخیره و مستقیماً پخش می‌شود؛ در غیر این صورت فقط کاور (`thumb_url`) و لینک پست اصلی (`original_url`) ارائه می‌شود. اگر دانلود کاور ناموفق باشد، مقدار `thumb_url` برابر `null` خواهد بود.
4. `audio`: فایل صوتی یا ویس؛ در صورت دانلود موفق، مسیر محلی در `local_audio_url` قرار می‌گیرد.
5. `document`: فایل ضمیمه غیرقابل‌پخش؛ فقط عنوان، حجم و لینک اصلی ذخیره می‌شود.

> فیلدهای داخلی `_remote_photos`، `_video_info` و `_audio_info` فقط در زمان اجرای Collector استفاده می‌شوند و پیش از نوشتن JSON حذف می‌شوند.

---

## ۴. ساختار ذخیره‌سازی وضعیت خوانده‌شده در کاربر (`localStorage`)

کلید در مرورگر مینی‌اپ: `bale_tg_viewer_state`

```json
{
  "read_state": {
    "durov": 531,
    "varzesh3": 128450
  },
  "last_active_channel": "durov"
}
```
* عدد مقابل هر کانال، شناسه آخرین پستی است که کاربر مشاهده کرده است. هر پیامی با شناسه بزرگتر از این عدد، نشانگر (Unread Badge) را در صفحه اصلی فعال می‌کند.
