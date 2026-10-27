# Bale Telegram Viewer

پروژه‌ای سبک، سرورلس (Serverless) و ۱۰۰٪ رایگان جهت مطالعه و مشاهده پست‌های کانال‌های عمومی تلگرام از داخل پیام‌رسان «بله» بدون نیاز به فیلترشکن.

---

## 📌 وضعیت کلی پروژه

تمامی بخش‌های فنی و مستندات پروژه به صورت کامل و تست‌شده پیاده‌سازی شده‌اند:

| مرحله | عنوان مرحله | وضعیت | مستندات و کدهای مربوطه |
| :---: | :--- | :---: | :--- |
| **۱** | **ساختار مخزن، فایل تنظیمات و طرح فرمت JSON** | ✅ تکمیل شد | [`config/channels.json`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/config/channels.json) \| [`docs/SCHEMA.md`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/docs/SCHEMA.md) |
| **۲** | **اسکریپت جمع‌کننده (Collector) و فشرده‌سازی مدیا** | ✅ تکمیل شد | [`collector/main.py`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/collector/main.py) \| [`collector/parser.py`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/collector/parser.py) |
| **۳** | **ورک‌فلو GitHub Actions (کرون، استقرار orphan)** | ✅ تکمیل شد | [`.github/workflows/collector.yml`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/.github/workflows/collector.yml) |
| **۴** | **مینی‌اپ فرانت‌اند (شبیه‌ساز تلگرام، تم بله، خوانده‌شده‌ها)** | ✅ تکمیل شد | [`web/index.html`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/web/index.html) \| [`web/app.js`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/web/app.js) \| [`web/style.css`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/web/style.css) |
| **۵** | **اتصال به پیام‌رسان بله (ربات و منوی وب‌اپ)** | ✅ تکمیل شد | [`bale/setup_bot.py`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/bale/setup_bot.py) |
| **۶** | **مستندات گام‌به‌گام راه‌اندازی و نگهداری** | ✅ تکمیل شد | [`docs/SETUP_GUIDE.md`](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/docs/SETUP_GUIDE.md) |

---

## 🚀 راهنمای سریع شروع به کار

برای راه‌اندازی سریع پروژه در کمتر از ۵ دقیقه:
1. مخزن را روی اکانت گیت‌هاب خود پوش کنید.
2. از مسیر `Settings > Pages` شاخه `gh-pages` را فعال کنید.
3. با دستور زیر دکمه منوی مینی‌اپ را روی ربات بله خود تنظیم کنید:
   ```bash
   python bale/setup_bot.py --token "<YOUR_BALE_BOT_TOKEN>" --url "https://<YOUR_USER>.github.io/<REPO>/"
   ```
4. برای راهنمای مصور و کامل، [راهنمای جامع راه‌اندازی (docs/SETUP_GUIDE.md)](file:///d:/Joud%20Files/Bale%20Telegram%20Viewer/docs/SETUP_GUIDE.md) را مطالعه کنید.

---

## 📂 ساختار فایل‌های مخزن

```text
Bale Telegram Viewer/
├── .github/
│   └── workflows/
│       └── collector.yml      # اتوماسیون کرون هر ۱۰ دقیقه و دیپلوی Orphan
├── config/
│   └── channels.json          # فهرست کانال‌ها و تنظیمات اسکرپر
├── collector/
│   ├── main.py                # نقطه ورود جمع‌کننده پست‌ها
│   ├── parser.py              # پارسر مقاوم تگ‌های HTML تلگرام
│   ├── media.py               # فشرده‌سازی عکس‌ها به WebP و پاکسازی انقضاشده‌ها
│   └── requirements.txt       # پکیج‌های پایتون (requests, bs4, Pillow)
├── web/
│   ├── index.html             # اسکلت اصلی مینی‌اپ با SDK رسمی بله
│   ├── app.js                 # منطق SPA، خوانده‌شده‌ها و تم بله
│   └── style.css              # استایل‌های شبیه‌ساز تلگرام (تم روشن و تاریک)
├── bale/
│   └── setup_bot.py           # اسکریپت راه‌اندازی دکمه Menu Button ربات بله
├── data/
│   ├── index.json             # منیفست سبک کانال‌ها برای صفحه اصلی
│   └── samples/               # داده‌های نمونه برای تست مستقل
├── docs/
│   ├── ARCHITECTURE.md        # مستندات کلان معماری و تصمیمات فنی
│   ├── SCHEMA.md              # مشخصات دقیق اسکیمای JSON
│   └── SETUP_GUIDE.md         # راهنمای صفر تا صد راه‌اندازی و اتصال به بله
├── .gitignore
└── README.md
```
