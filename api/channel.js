/**
 * فانکشن سرورلس جستجو و استخراج آنی پست‌های تلگرام (Real-Time Channel Scraper)
 * دریافت صفحه عمومی تلگرام، پارس داده‌ها و بازنویسی آدرس عکس‌ها به پروکسی بدون فیلتر.
 */

export default async function handler(req, res) {
  // هدرهای CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  let { id } = req.query;
  if (!id) {
    return res.status(400).json({ error: 'شناسه کانال الزامی است.' });
  }

  // تمیزکاری ورودی
  id = String(id).replace(/^https?:\/\/t\.me\/(s\/)?/i, '').replace(/^@/, '').trim().replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();

  if (!id || id.length < 4) {
    return res.status(400).json({ error: 'شناسه کانال نامعتبر است (حداقل ۴ کاراکتر).' });
  }

  try {
    const url = `https://t.me/s/${id}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fa,en-US;q=0.9,en;q=0.8'
      }
    });

    if (response.status === 404) {
      return res.status(404).json({ error: `کانال '${id}' در تلگرام یافت نشد.` });
    }

    const html = await response.text();

    // بررسی کانال‌های خصوصی یا مسدود
    if (html.includes("can't be displayed") || html.includes('Contact @') || !html.includes('tgme_widget_message_wrap')) {
      return res.status(400).json({ error: `کانال '${id}' یک کانال عمومی با پیش‌نمایش وب نیست یا امکان مشاهده ندارد.` });
    }

    // پارس اطلاعات کانال و پست‌ها
    const data = parseTelegramHtml(html, id);
    res.setHeader('Cache-Control', 'public, max-age=120, s-maxage=120, stale-while-revalidate=60');
    return res.status(200).json(data);

  } catch (err) {
    return res.status(500).json({ error: 'خطای سرور در استخراج تلگرام: ' + err.message });
  }
}

/**
 * پارس اطلاعات و پیام‌های صفحه وب تلگرام
 */
function parseTelegramHtml(html, channelId) {
  // متادیتای کانال
  const titleMatch = html.match(/<div class="[^"]*(?:tgme_channel_info_header_title|tgme_page_title)[^"]*"><span[^>]*>(.*?)<\/span>/i) ||
                     html.match(/<div class="[^"]*(?:tgme_channel_info_header_title|tgme_page_title)[^"]*">(.*?)<\/div>/i);
  const title = titleMatch ? cleanText(titleMatch[1]) : channelId;

  const descMatch = html.match(/<div class="[^"]*(?:tgme_channel_info_description|tgme_page_description)[^"]*">(.*?)<\/div>/i);
  const description = descMatch ? cleanText(descMatch[1]) : '';

  const avatarMatch = html.match(/<img class="[^"]*(?:tgme_page_photo_image|tgme_channel_info_header_avatar)[^"]*" src="([^"]+)"/i);
  const rawAvatar = avatarMatch ? avatarMatch[1] : null;
  const avatar = rawAvatar ? `/api/image?url=${encodeURIComponent(rawAvatar)}` : null;

  const subsMatch = html.match(/<span class="counter_value">([^<]+)<\/span>/i);
  const subscribers = subsMatch ? subsMatch[1].trim() : null;

  // استخراج پیام‌ها
  const messages = [];
  const wrapRegex = /<div class="tgme_widget_message_wrap[\s\S]*?<\/div>\s*<\/div>\s*<\/div>/gi;
  const rawWraps = html.split('<div class="tgme_widget_message_wrap');

  for (let i = 1; i < rawWraps.length; i++) {
    const wrap = '<div class="tgme_widget_message_wrap' + rawWraps[i];

    // شناسه پست
    const postMatch = wrap.match(/data-post="[^/]+\/(\d+)"/i);
    if (!postMatch) continue;
    const postId = parseInt(postMatch[1], 10);

    // تاریخ
    const timeMatch = wrap.match(/<time datetime="([^"]+)"/i);
    const dateIso = timeMatch ? timeMatch[1] : null;
    const timestamp = dateIso ? Math.floor(new Date(dateIso).getTime() / 1000) : 0;

    // بازدیدها
    const viewsMatch = wrap.match(/<span class="tgme_widget_message_views">([^<]+)<\/span>/i);
    const views = viewsMatch ? viewsMatch[1].trim() : null;

    // متن پیام
    const textMatch = wrap.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/i);
    let textHtml = textMatch ? sanitizeMessageText(textMatch[1]) : '';

    // عکس‌ها
    const photos = [];
    const photoRegex = /background-image:url\(['"]?(https:\/\/[^'"]+)['"]?\)/gi;
    let pMatch;
    while ((pMatch = photoRegex.exec(wrap)) !== null) {
      const remoteUrl = pMatch[1];
      if (remoteUrl.includes('telesco.pe') || remoteUrl.includes('cdn')) {
        photos.push({
          url: `/api/image?url=${encodeURIComponent(remoteUrl)}`,
          remote_url: remoteUrl
        });
      }
    }

    // ویدیو
    let mediaType = photos.length > 0 ? 'photo' : 'none';
    let videoInfo = null;

    if (wrap.includes('tgme_widget_message_video')) {
      mediaType = 'video_link';
      const durMatch = wrap.match(/class="[^"]*(?:message_video_duration|tgme_widget_message_video_duration)[^"]*">([^<]+)<\/span>/i);
      const duration = durMatch ? durMatch[1].trim() : null;
      const thumbUrl = photos.length > 0 ? photos[0].url : null;

      videoInfo = {
        duration,
        thumb_url: thumbUrl,
        original_url: `https://t.me/${channelId}/${postId}`
      };
    }

    // پاسخ (Reply)
    let replyTo = null;
    const replyMatch = wrap.match(/<a class="tgme_widget_message_reply[^"]*" href="[^"]*\/(\d+)"[^>]*>[\s\S]*?<div class="tgme_widget_message_metatext">([\s\S]*?)<\/div>/i);
    if (replyMatch) {
      replyTo = {
        id: parseInt(replyMatch[1], 10),
        text_snippet: cleanText(replyMatch[2]).slice(0, 80)
      };
    }

    // فوروارد
    let forwardFrom = null;
    const fwdMatch = wrap.match(/<a class="tgme_widget_message_forwarded_from_name"[^>]*>([\s\S]*?)<\/a>/i);
    if (fwdMatch) {
      forwardFrom = cleanText(fwdMatch[1]);
    }

    messages.push({
      id: postId,
      date: dateIso,
      timestamp,
      text_html: textHtml,
      views,
      media_type: mediaType,
      media: {
        photos,
        video: videoInfo
      },
      forward_from: forwardFrom,
      reply_to: replyTo,
      original_url: `https://t.me/${channelId}/${postId}`
    });
  }

  // مرتب‌سازی قدیم به جدید
  messages.sort((a, b) => a.id - b.id);

  return {
    channel: {
      id: channelId,
      title,
      avatar,
      description,
      subscribers,
      last_updated: Math.floor(Date.now() / 1000)
    },
    messages
  };
}

function cleanText(str) {
  if (!str) return '';
  return str.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').trim();
}

function sanitizeMessageText(rawHtml) {
  if (!rawHtml) return '';
  // حذف تگ‌های غیرمجاز و حفظ فرمت اصلی
  return rawHtml
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<a\s+href="([^"]+)"[^>]*>/gi, '<a href="$1" target="_blank" rel="noopener noreferrer">');
}
