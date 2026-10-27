/**
 * Deno Deploy Serverless Entry Point
 * سرورلس آنی بدون نیاز به شماره تلفن و کاملاً مستقل از کلادفلر
 */

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const path = url.pathname;

  // هدرهای CORS برای تمام درخواست‌ها
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
  };

  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  // ۱. روت استخراج آنی کانال: /api/channel?id=<channel_id>
  if (path === "/api/channel") {
    let id = url.searchParams.get("id") || "";
    id = id.replace(/^https?:\/\/t\.me\/(s\/)?/i, "").replace(/^@/, "").trim().replace(/[^a-zA-Z0-9_]/g, "").toLowerCase();

    if (!id || id.length < 4) {
      return new Response(JSON.stringify({ error: "شناسه کانال نامعتبر است." }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }

    try {
      const tgUrl = `https://t.me/s/${id}`;
      const upstream = await fetch(tgUrl, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
          "Accept-Language": "fa,en;q=0.9"
        }
      });

      if (upstream.status === 404) {
        return new Response(JSON.stringify({ error: `کانال '${id}' در تلگرام یافت نشد.` }), {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      }

      const html = await upstream.text();
      if (html.includes("can't be displayed") || html.includes("Contact @") || !html.includes("tgme_widget_message_wrap")) {
        return new Response(JSON.stringify({ error: `کانال '${id}' یک کانال عمومی با پیش‌نمایش وب نیست.` }), {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      }

      const data = parseTelegramHtml(html, id);
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=60, s-maxage=60"
        }
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: "خطای سرور: " + e.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }
  }

  // ۲. روت پروکسی عکس: /api/image?url=<encoded_url>
  if (path === "/api/image") {
    const targetUrl = url.searchParams.get("url");
    if (!targetUrl) {
      return new Response("Missing url param", { status: 400, headers: corsHeaders });
    }

    try {
      const decoded = decodeURIComponent(targetUrl);
      const parsed = new URL(decoded);
      if (!parsed.hostname.includes("telesco.pe") && !parsed.hostname.includes("t.me")) {
        return new Response("Forbidden host", { status: 403, headers: corsHeaders });
      }

      const imgResp = await fetch(decoded, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "Referer": "https://t.me/"
        }
      });

      if (!imgResp.ok) {
        return new Response("Failed to fetch image", { status: imgResp.status, headers: corsHeaders });
      }

      const contentType = imgResp.headers.get("content-type") || "image/jpeg";
      const blob = await imgResp.arrayBuffer();

      return new Response(blob, {
        status: 200,
        headers: {
          ...corsHeaders,
          "Content-Type": contentType,
          "Cache-Control": "public, max-age=86400, s-maxage=86400"
        }
      });
    } catch (e) {
      return new Response("Proxy error: " + e.message, { status: 500, headers: corsHeaders });
    }
  }

  // سایر روت‌ها به صفحه اصلی گیت‌هاب پیجز هدایت می‌شوند
  return Response.redirect("https://jkiani89.github.io/bale-telegram-viewer/", 302);
});

function parseTelegramHtml(html: string, channelId: string) {
  const titleMatch = html.match(/<div class="[^"]*(?:tgme_channel_info_header_title|tgme_page_title)[^"]*"><span[^>]*>(.*?)<\/span>/i) ||
                     html.match(/<div class="[^"]*(?:tgme_channel_info_header_title|tgme_page_title)[^"]*">(.*?)<\/div>/i);
  const title = titleMatch ? clean(titleMatch[1]) : channelId;

  const descMatch = html.match(/<div class="[^"]*(?:tgme_channel_info_description|tgme_page_description)[^"]*">(.*?)<\/div>/i);
  const description = descMatch ? clean(descMatch[1]) : "";

  const avatarMatch = html.match(/<img class="[^"]*(?:tgme_page_photo_image|tgme_channel_info_header_avatar)[^"]*" src="([^"]+)"/i);
  const rawAvatar = avatarMatch ? avatarMatch[1] : null;
  const avatar = rawAvatar ? `/api/image?url=${encodeURIComponent(rawAvatar)}` : null;

  const subsMatch = html.match(/<span class="counter_value">([^<]+)<\/span>/i);
  const subscribers = subsMatch ? subsMatch[1].trim() : null;

  const messages = [];
  const rawWraps = html.split('<div class="tgme_widget_message_wrap');

  for (let i = 1; i < rawWraps.length; i++) {
    const wrap = '<div class="tgme_widget_message_wrap' + rawWraps[i];
    const postMatch = wrap.match(/data-post="[^/]+\/(\d+)"/i);
    if (!postMatch) continue;
    const postId = parseInt(postMatch[1], 10);

    const timeMatch = wrap.match(/<time datetime="([^"]+)"/i);
    const dateIso = timeMatch ? timeMatch[1] : null;
    const timestamp = dateIso ? Math.floor(new Date(dateIso).getTime() / 1000) : 0;

    const viewsMatch = wrap.match(/<span class="tgme_widget_message_views">([^<]+)<\/span>/i);
    const views = viewsMatch ? viewsMatch[1].trim() : null;

    const textMatch = wrap.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/i);
    const textHtml = textMatch ? cleanHtml(textMatch[1]) : "";

    const photos = [];
    const photoRegex = /background-image:url\(['"]?(https:\/\/[^'"]+)['"]?\)/gi;
    let pMatch;
    while ((pMatch = photoRegex.exec(wrap)) !== null) {
      photos.push({
        url: `/api/image?url=${encodeURIComponent(pMatch[1])}`,
        remote_url: pMatch[1]
      });
    }

    let mediaType = photos.length > 0 ? "photo" : "none";
    let videoInfo = null;
    if (wrap.includes("tgme_widget_message_video")) {
      mediaType = "video_link";
      const durMatch = wrap.match(/class="[^"]*(?:message_video_duration|tgme_widget_message_video_duration)[^"]*">([^<]+)<\/span>/i);
      videoInfo = {
        duration: durMatch ? durMatch[1].trim() : null,
        thumb_url: photos.length > 0 ? photos[0].url : null,
        original_url: `https://t.me/${channelId}/${postId}`
      };
    }

    messages.push({
      id: postId,
      date: dateIso,
      timestamp,
      text_html: textHtml,
      views,
      media_type: mediaType,
      media: { photos, video: videoInfo },
      original_url: `https://t.me/${channelId}/${postId}`
    });
  }

  messages.sort((a, b) => a.id - b.id);
  return {
    channel: { id: channelId, title, avatar, description, subscribers, last_updated: Math.floor(Date.now() / 1000) },
    messages
  };
}

function clean(s: string) {
  return s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim();
}

function cleanHtml(s: string) {
  return s.replace(/<script[\s\S]*?<\/script>/gi, "").replace(/<style[\s\S]*?<\/style>/gi, "");
}
