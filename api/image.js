/**
 * پروکسی سرورلس تصاویر تلگرام (Zero-VPN Image Proxy)
 * دریافت تصویر از cdn*.telesco.pe و تحویل امن به کلاینت داخل ایران
 */

export default async function handler(req, res) {
  // تنظیم هدرهای CORS برای دسترسی بدون محدودیت
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { url } = req.query;
  if (!url) {
    return res.status(400).send('پارامتر url الزامی است.');
  }

  try {
    const targetUrl = decodeURIComponent(url);
    const parsed = new URL(targetUrl);

    // اعتبارسنجی امنیتی: فقط دامنه‌های معتبر مدیا تلگرام مجاز هستند
    const allowedSuffixes = ['telesco.pe', 't.me', 'telegram.org'];
    const isAllowed = allowedSuffixes.some(domain => parsed.hostname === domain || parsed.hostname.endsWith('.' + domain));

    if (!isAllowed) {
      return res.status(403).send('دامنه درخواستی مجاز نیست.');
    }

    // دریافت تصویر از تلگرام با هدرهای استاندارد مرورگر
    const upstream = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://t.me/'
      }
    });

    if (!upstream.ok) {
      return res.status(upstream.status).send(`خطای دریافت از تلگرام: ${upstream.status}`);
    }

    const contentType = upstream.headers.get('content-type') || 'image/jpeg';
    res.setHeader('Content-Type', contentType);
    // کش کردن در مرورگر و سرورلس برای ۱ روز جهت سرعت بی‌نظیر
    res.setHeader('Cache-Control', 'public, max-age=86400, s-maxage=86400, stale-while-revalidate=43200');

    const arrayBuffer = await upstream.arrayBuffer();
    return res.status(200).send(Buffer.from(arrayBuffer));

  } catch (err) {
    return res.status(500).send('خطای پروکسی تصویر: ' + err.message);
  }
}
