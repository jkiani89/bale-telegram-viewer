/**
 * Bale Telegram Viewer - Client SPA Logic
 * رابط کاربری سبک، بهینه‌شده برای مرورگر وب‌ویوی بله
 */

// وضعیت سراسری برنامه
const state = {
  currentView: 'channels', // 'channels' | 'feed'
  activeChannelId: null,
  channels: [],
  activeChannelFeed: null,
  searchQuery: '',
  readState: {}, // { [channelId]: lastReadMsgId }
};

// ==========================================================================
// مقداردهی اولیه و همگام‌سازی با SDK بله
// ==========================================================================

function initBaleSDK() {
  if (window.Bale && window.Bale.WebApp) {
    const webApp = window.Bale.WebApp;
    try {
      webApp.ready();
      webApp.expand();

      // همگام‌سازی رنگ‌بندی و تم با بله
      applyBaleTheme(webApp);

      // اتصال رویداد دکمه بازگشت بله (Native Back Button)
      if (webApp.BackButton) {
        webApp.BackButton.onClick(() => {
          if (state.currentView === 'feed') {
            showChannelsView();
          }
        });
      }
    } catch (e) {
      console.warn('خطا در فراخوانی متدهای SDK بله:', e);
    }
  } else {
    // تطبیق با تم سیستم در صورت اجرا خارج از بله
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      document.body.classList.add('theme-dark');
    }
  }
}

function applyBaleTheme(webApp) {
  const params = webApp.themeParams;
  if (!params) return;

  const root = document.documentElement;
  if (params.bg_color) root.style.setProperty('--surface-color', params.bg_color);
  if (params.secondary_bg_color) root.style.setProperty('--bg-color', params.secondary_bg_color);
  if (params.text_color) root.style.setProperty('--text-primary', params.text_color);
  if (params.hint_color) root.style.setProperty('--text-secondary', params.hint_color);
  if (params.button_color) {
    root.style.setProperty('--accent-color', params.button_color);
    root.style.setProperty('--header-bg', params.button_color);
    root.style.setProperty('--unread-badge-bg', params.button_color);
  }
  if (params.button_text_color) root.style.setProperty('--header-text', params.button_text_color);

  // تشخیص خودکار حالت تاریک
  if (webApp.colorScheme === 'dark' || isColorDark(params.bg_color)) {
    document.body.classList.add('theme-dark');
  } else {
    document.body.classList.remove('theme-dark');
  }
}

function isColorDark(hexColor) {
  if (!hexColor || !hexColor.startsWith('#')) return false;
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substr(0, 2), 16);
  const g = parseInt(hex.substr(2, 2), 16);
  const b = parseInt(hex.substr(4, 2), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness < 128;
}

// ==========================================================================
// مدیریت ذخیره‌سازی محلی (LocalStorage - Read State)
// ==========================================================================

const STORAGE_KEY = 'bale_tg_viewer_state_v1';

function loadReadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      state.readState = parsed.read_state || {};
    }
  } catch (e) {
    console.error('خطا در خواندن localStorage:', e);
    state.readState = {};
  }
}

function markChannelAsRead(channelId, highestMsgId) {
  if (!highestMsgId) return;
  state.readState[channelId] = highestMsgId;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      read_state: state.readState,
      last_active: channelId,
      updated_at: Date.now()
    }));
  } catch (e) {
    console.error('خطا در ذخیره localStorage:', e);
  }
}

// ==========================================================================
// دریافت داده‌ها از GitHub Pages CDN با ضدکش (Cache-Busting)
// ==========================================================================

async function fetchIndexData() {
  const cacheBuster = `t=${Date.now()}`;
  try {
    const resp = await fetch(`data/index.json?${cacheBuster}`, { cache: 'no-cache' });
    if (!resp.ok) {
      // اگر روی محیط توسعه هنوز داده تولید نشده بود، به samples برود
      const fallback = await fetch(`data/samples/index.json?${cacheBuster}`);
      return await fallback.json();
    }
    return await resp.json();
  } catch (e) {
    console.warn('دسترسی به data/index.json ممکن نشد، بارگذاری سمپل:', e);
    const fallback = await fetch(`data/samples/index.json?${cacheBuster}`);
    return await fallback.json();
  }
}

async function fetchChannelFeed(channelId) {
  const cacheBuster = `t=${Date.now()}`;
  try {
    const resp = await fetch(`data/${channelId}.json?${cacheBuster}`, { cache: 'no-cache' });
    if (!resp.ok) {
      const fallback = await fetch(`data/samples/${channelId}.json?${cacheBuster}`);
      return await fallback.json();
    }
    return await resp.json();
  } catch (e) {
    console.warn(`خطا در دریافت data/${channelId}.json، بارگذاری سمپل:`, e);
    const fallback = await fetch(`data/samples/${channelId}.json?${cacheBuster}`);
    return await fallback.json();
  }
}

// ==========================================================================
// مدیریت کانال‌های حذف‌شده توسط کاربر (Hidden / Deleted Channels)
// ==========================================================================

const HIDDEN_CHANNELS_KEY = 'bale_tg_hidden_channels';

function getHiddenChannels() {
  try {
    const raw = localStorage.getItem(HIDDEN_CHANNELS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function hideChannel(channelId) {
  const list = getHiddenChannels();
  if (!list.includes(channelId)) {
    list.push(channelId);
    localStorage.setItem(HIDDEN_CHANNELS_KEY, JSON.stringify(list));
  }
}

let pendingDeleteChannelId = null;

function initDeleteChannelModal() {
  const modal = document.getElementById('deleteChannelModal');
  const closeBtn = document.getElementById('closeDeleteModal');
  const cancelBtn = document.getElementById('cancelDeleteBtn');
  const confirmBtn = document.getElementById('confirmDeleteBtn');

  const closeModal = () => {
    modal.style.display = 'none';
    pendingDeleteChannelId = null;
  };

  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  confirmBtn.addEventListener('click', () => {
    if (pendingDeleteChannelId) {
      hideChannel(pendingDeleteChannelId);
      state.channels = state.channels.filter(c => c.id !== pendingDeleteChannelId);
      renderChannelsList();
      closeModal();
    }
  });
}

function openDeleteChannelModal(channelId) {
  pendingDeleteChannelId = channelId;
  const ch = state.channels.find(c => c.id === channelId);
  const modal = document.getElementById('deleteChannelModal');
  const textEl = document.getElementById('deleteModalText');
  
  textEl.textContent = `آیا می‌خواهید کانال «${ch ? ch.title : channelId}» از لیست کانال‌های شما حذف شود؟`;
  modal.style.display = 'flex';
}

// ==========================================================================
// رندرینگ رابط کاربری (UI Rendering)
// ==========================================================================

function renderChannelsList() {
  const container = document.getElementById('channelsList');
  if (!container) return;

  const hiddenList = getHiddenChannels();
  const visibleChannels = state.channels.filter(c => !hiddenList.includes(c.id));

  const query = state.searchQuery.trim().toLowerCase();
  const filtered = visibleChannels.filter(ch => {
    if (!query) return true;
    return (
      (ch.title && ch.title.toLowerCase().includes(query)) ||
      (ch.description && ch.description.toLowerCase().includes(query)) ||
      (ch.id && ch.id.toLowerCase().includes(query))
    );
  });

  if (filtered.length === 0) {
    const cleanQ = query.replace(/^@/, '').replace(/[^a-zA-Z0-9_]/g, '');
    const isPotentialId = cleanQ.length >= 4;

    container.innerHTML = `
      <div class="empty-state">
        <p>کانالی با عبارت «${escapeHtml(query)}» یافت نشد.</p>
        ${isPotentialId ? `
          <div class="online-search-card">
            <div class="online-search-header">
              <span class="online-badge">⚡ آنلاین</span>
              <h4>افزودن مستقیم به مینی‌اپ</h4>
            </div>
            <p>می‌توانید کانال عمومی <b>@${escapeHtml(cleanQ)}</b> را مستقیماً دریافت و به لیست اضافه کنید:</p>
            <button class="btn btn-primary" id="btnSearchOnlineNow">
              🔍 دریافت فوری پست‌های @${escapeHtml(cleanQ)}
            </button>
          </div>
        ` : ''}
      </div>
    `;

    if (isPotentialId) {
      const btn = document.getElementById('btnSearchOnlineNow');
      if (btn) {
        btn.addEventListener('click', () => {
          btn.disabled = true;
          btn.textContent = 'در حال استخراج پست‌ها از تلگرام...';
          triggerDirectChannelAdd(
            cleanQ,
            (progressText) => {
              btn.textContent = progressText;
            },
            (successText) => {
              btn.textContent = successText;
              setTimeout(() => {
                openChannelFeed(cleanQ);
              }, 1200);
            },
            (errorText) => {
              alert(errorText);
              btn.disabled = false;
              btn.textContent = `🔍 دریافت فوری پست‌های @${cleanQ}`;
            }
          );
        });
      }
    }
    return;
  }

  container.innerHTML = filtered.map(ch => {
    const lastPostId = ch.last_post ? ch.last_post.id : 0;
    const lastReadId = state.readState[ch.id] || 0;
    const isUnread = lastPostId > lastReadId;

    const formattedTime = ch.last_post && ch.last_post.timestamp
      ? formatRelativeTime(ch.last_post.timestamp)
      : '';

    const avatarHtml = ch.avatar
      ? `<img src="${ch.avatar}" class="channel-avatar" alt="${escapeHtml(ch.title)}" onerror="this.outerHTML='<div class=\\'channel-avatar\\'>${escapeHtml(ch.title.charAt(0))}</div>'">`
      : `<div class="channel-avatar">${escapeHtml(ch.title.charAt(0))}</div>`;

    return `
      <div class="channel-item" data-channel-id="${escapeHtml(ch.id)}">
        <div class="channel-avatar-wrap">
          ${avatarHtml}
        </div>
        <div class="channel-info">
          <div class="channel-top-row">
            <div class="channel-title-group">
              <span class="channel-name">${escapeHtml(ch.title)}</span>
              <span class="verified-badge" title="تایید شده">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              </span>
            </div>
            <span class="channel-time">${formattedTime}</span>
          </div>
          <div class="channel-bottom-row">
            <span class="channel-snippet">${escapeHtml(ch.last_post ? ch.last_post.snippet : ch.description || '')}</span>
            ${isUnread ? `<span class="unread-badge">جدید</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');

  // رویدادهای لمس طولانی (Long-Press) و کلیک
  container.querySelectorAll('.channel-item').forEach(el => {
    const chId = el.getAttribute('data-channel-id');
    let pressTimer = null;
    let didLongPress = false;

    const startPress = () => {
      didLongPress = false;
      el.classList.add('long-pressing');
      pressTimer = setTimeout(() => {
        didLongPress = true;
        el.classList.remove('long-pressing');
        if (navigator.vibrate) {
          try { navigator.vibrate(60); } catch(e) {}
        }
        openDeleteChannelModal(chId);
      }, 600);
    };

    const cancelPress = () => {
      clearTimeout(pressTimer);
      el.classList.remove('long-pressing');
    };

    // رویدادهای لمسی موبایل
    el.addEventListener('touchstart', startPress, { passive: true });
    el.addEventListener('touchend', cancelPress);
    el.addEventListener('touchmove', cancelPress);

    // رویدادهای ماوس دسکتاپ
    el.addEventListener('mousedown', startPress);
    el.addEventListener('mouseup', cancelPress);
    el.addEventListener('mouseleave', cancelPress);

    el.addEventListener('click', (e) => {
      if (didLongPress) {
        didLongPress = false;
        e.preventDefault();
        return;
      }
      openChannelFeed(chId);
    });
  });
}

// ==========================================================================
// جستجوی آنلاین لحظه‌ای (Real-Time Live Search)
// ==========================================================================

async function fetchAndShowOnlineChannel(channelId) {
  state.activeChannelId = channelId;
  state.currentView = 'feed';

  const backBtn = document.getElementById('backBtn');
  backBtn.style.display = 'flex';

  document.getElementById('headerTitle').textContent = `@${channelId}`;
  document.getElementById('headerSubtitle').textContent = 'در حال جستجوی آنلاین...';

  document.getElementById('channelsView').style.display = 'none';
  const feedView = document.getElementById('feedView');
  feedView.style.display = 'flex';

  const messagesList = document.getElementById('messagesList');
  messagesList.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>در حال ارتباط با تلگرام و استخراج زنده پست‌های <b>@${escapeHtml(channelId)}</b>...</p>
    </div>
  `;

  if (window.Bale && window.Bale.WebApp && window.Bale.WebApp.BackButton) {
    try { window.Bale.WebApp.BackButton.show(); } catch (e) {}
  }

  window.scrollTo(0, 0);

  try {
    const resp = await fetch(`/api/channel?id=${encodeURIComponent(channelId)}`);
    const data = await resp.json();

    if (!resp.ok || data.error) {
      messagesList.innerHTML = `
        <div class="empty-state">
          <p style="color: #ef4444; font-weight: 700;">خطا در دریافت کانال:</p>
          <p>${escapeHtml(data.error || 'کانال پیدا نشد یا خصوصی است.')}</p>
          <button class="btn btn-primary" onclick="showChannelsView()" style="margin-top: 14px;">
            بازگشت به لیست کانال‌ها
          </button>
        </div>
      `;
      document.getElementById('headerSubtitle').textContent = 'خطا در بارگذاری';
      return;
    }

    state.activeChannelFeed = data;
    if (data.channel) {
      document.getElementById('headerTitle').textContent = data.channel.title || channelId;
      document.getElementById('headerSubtitle').textContent = data.channel.subscribers 
        ? `${data.channel.subscribers} دنبال‌کننده (زنده)` 
        : 'کانال تلگرام (زنده)';
    }

    renderFeedMessages();

  } catch (err) {
    messagesList.innerHTML = `
      <div class="empty-state">
        <p style="color: #ef4444;">ارتباط با سرورلس برقرار نشد.</p>
        <p style="font-size: 0.8rem; opacity: 0.8;">${escapeHtml(err.message)}</p>
        <button class="btn btn-primary" onclick="showChannelsView()" style="margin-top: 14px;">
          بازگشت
        </button>
      </div>
    `;
  }
}

async function openChannelFeed(channelId) {
  state.activeChannelId = channelId;
  state.currentView = 'feed';

  // تغییر ظاهر هدر
  const backBtn = document.getElementById('backBtn');
  backBtn.style.display = 'flex';

  const channelMeta = state.channels.find(c => c.id === channelId);
  document.getElementById('headerTitle').textContent = channelMeta ? channelMeta.title : channelId;
  document.getElementById('headerSubtitle').textContent = 'در حال بارگذاری...';

  // نمایش ویوی فید
  document.getElementById('channelsView').style.display = 'none';
  const feedView = document.getElementById('feedView');
  feedView.style.display = 'flex';

  const messagesList = document.getElementById('messagesList');
  messagesList.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>در حال دریافت پست‌های تلگرام...</p>
    </div>
  `;

  // نمایش Back Button در SDK بله
  if (window.Bale && window.Bale.WebApp && window.Bale.WebApp.BackButton) {
    try { window.Bale.WebApp.BackButton.show(); } catch (e) {}
  }

  // اسکرول به بالا
  window.scrollTo(0, 0);

  // دریافت فید
  const feedData = await fetchChannelFeed(channelId);
  state.activeChannelFeed = feedData;

  if (feedData && feedData.channel) {
    const subs = feedData.channel.subscribers ? `${feedData.channel.subscribers} دنبال‌کننده` : 'کانال تلگرام';
    document.getElementById('headerSubtitle').textContent = subs;
  }

  const previousLastReadId = state.readState[channelId] || 0;
  renderFeedMessages(previousLastReadId);

  // ثبت به عنوان خوانده‌شده بعد از تشخیص نشانگر اولین پیام جدید
  if (feedData && feedData.messages && feedData.messages.length > 0) {
    const highestId = Math.max(...feedData.messages.map(m => m.id));
    markChannelAsRead(channelId, highestId);
  }
}

function renderFeedMessages(previousLastReadId = 0) {
  const container = document.getElementById('messagesList');
  if (!container || !state.activeChannelFeed) return;

  const messages = state.activeChannelFeed.messages || [];
  const query = state.searchQuery.trim().toLowerCase();

  const filtered = messages.filter(m => {
    if (!query) return true;
    return m.text_html && m.text_html.toLowerCase().includes(query);
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>هیچ پیامی در این کانال یافت نشد.</p>
      </div>
    `;
    return;
  }

  let lastDateStr = '';
  let firstUnreadFound = false;
  const htmlParts = [];

  filtered.forEach(msg => {
    // تقسیم‌کننده تاریخ (Date Divider)
    const msgDateStr = formatDateGroup(msg.timestamp);
    if (msgDateStr !== lastDateStr) {
      htmlParts.push(`
        <div class="date-divider">
          <span class="date-divider-pill">${msgDateStr}</span>
        </div>
      `);
      lastDateStr = msgDateStr;
    }

    // نشانگر خط اولین پیام جدید خوانده‌نشده
    if (!firstUnreadFound && previousLastReadId > 0 && msg.id > previousLastReadId) {
      firstUnreadFound = true;
      htmlParts.push(`
        <div class="unread-separator" id="first-unread-separator">
          <span>🔻 پیام‌های جدید (خوانده‌نشده)</span>
        </div>
      `);
    }

    // مدیا (عکس‌ها)
    let mediaHtml = '';
    if (msg.media && msg.media.photos && msg.media.photos.length > 0) {
      mediaHtml = msg.media.photos.map(p => `
        <div class="message-media-wrap">
          <img src="${p.url}" alt="تصویر پیام" loading="lazy" class="zoomable-img" data-full-url="${p.url}">
        </div>
      `).join('');
    }

    // کارت اختصاصی ویدیو (پخش زنده یا لینک تلگرام)
    let videoHtml = '';
    if (msg.media && msg.media.video) {
      const v = msg.media.video;
      const thumbSrc = v.thumb_url || (msg.media.photos && msg.media.photos[0] ? msg.media.photos[0].url : '');
      if (v.local_video_url) {
        // ویدیوی زیر ۱۲ مگابایت دانلودشده جهت پخش مستقیم
        videoHtml = `
          <div class="video-card-wrap">
            <video src="${v.local_video_url}" poster="${thumbSrc || ''}" controls playsinline preload="metadata" class="chat-video-player"></video>
          </div>
        `;
      } else {
        // ویدیوی سنگین بالای ۱۲ مگابایت
        videoHtml = `
          <div class="video-card-wrap">
            ${thumbSrc ? `<img src="${thumbSrc}" class="video-thumb" alt="کاور ویدیو">` : ''}
            <div class="video-play-overlay">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
            </div>
            ${v.duration ? `<span class="video-duration-badge">${escapeHtml(v.duration)}</span>` : ''}
          </div>
          <a href="${msg.original_url}" target="_blank" rel="noopener noreferrer" class="video-open-btn">
            مشاهده ویدیو در تلگرام
          </a>
        `;
      }
    }

    // صوت و ویس (Voice & Audio Player)
    let audioHtml = '';
    if (msg.media && msg.media.audio && msg.media.audio.local_audio_url) {
      const a = msg.media.audio;
      audioHtml = `
        <div class="chat-audio-wrap">
          <span class="chat-audio-title">🎵 ${escapeHtml(a.title || 'پیام صوتی')} ${a.duration ? `(${escapeHtml(a.duration)})` : ''}</span>
          <audio src="${a.local_audio_url}" controls class="chat-audio-player" preload="metadata"></audio>
        </div>
      `;
    }

    // پیش‌نمایش پاسخ (Reply)
    let replyHtml = '';
    if (msg.reply_to) {
      replyHtml = `
        <div class="message-reply-preview">
          <div class="message-reply-author">پاسخ به پیام</div>
          <div>${escapeHtml(msg.reply_to.text_snippet || '')}</div>
        </div>
      `;
    }

    // فوروارد شده
    let forwardHtml = '';
    if (msg.forward_from) {
      forwardHtml = `
        <div class="message-forward-header">
          فوروارد شده از ${escapeHtml(msg.forward_from)}
        </div>
      `;
    }

    // ساعت پیام
    const msgTime = formatClockTime(msg.timestamp);

    htmlParts.push(`
      <div class="message-bubble" id="msg-${msg.id}">
        ${forwardHtml}
        ${replyHtml}
        ${mediaHtml}
        ${videoHtml}
        ${audioHtml}
        ${msg.text_html ? `<div class="message-text">${msg.text_html}</div>` : ''}
        <div class="message-meta">
          ${msg.views ? `
            <span class="meta-views">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
              ${escapeHtml(msg.views)}
            </span>
          ` : ''}
          <span class="meta-time">${msgTime}</span>
        </div>
      </div>
    `);
  });

  container.innerHTML = htmlParts.join('');

  // اسکرول هوشمند: به اولین پیام خوانده‌نشده یا به انتهای چت
  setTimeout(() => {
    const unreadMarker = document.getElementById('first-unread-separator');
    if (unreadMarker) {
      unreadMarker.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
  }, 150);

  // اتصال رویداد زوم لایت‌باکس روی عکس‌ها
  container.querySelectorAll('.zoomable-img').forEach(img => {
    img.addEventListener('click', () => {
      openLightbox(img.getAttribute('data-full-url') || img.src);
    });
  });
}

function showChannelsView() {
  state.currentView = 'channels';
  state.activeChannelId = null;
  state.activeChannelFeed = null;

  document.getElementById('backBtn').style.display = 'none';
  document.getElementById('headerTitle').textContent = 'کانال‌های تلگرام';
  document.getElementById('headerSubtitle').textContent = 'بدون فیلترشکن';

  document.getElementById('feedView').style.display = 'none';
  document.getElementById('channelsView').style.display = 'flex';

  if (window.Bale && window.Bale.WebApp && window.Bale.WebApp.BackButton) {
    try { window.Bale.WebApp.BackButton.hide(); } catch (e) {}
  }

  renderChannelsList();
}

// ==========================================================================
// لایت‌باکس نمایش تمام‌صفحه تصاویر
// ==========================================================================

function initLightbox() {
  const modal = document.getElementById('lightboxModal');
  const overlay = document.getElementById('lightboxOverlay');
  const closeBtn = document.getElementById('lightboxClose');

  const closeFn = () => { modal.style.display = 'none'; };

  overlay.addEventListener('click', closeFn);
  closeBtn.addEventListener('click', closeFn);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display !== 'none') {
      closeFn();
    }
  });
}

function openLightbox(url) {
  const modal = document.getElementById('lightboxModal');
  const img = document.getElementById('lightboxImg');
  img.src = url;
  modal.style.display = 'flex';
}

// ==========================================================================
// فرمت‌بندی تاریخ و زمان فارسی
// ==========================================================================

function formatRelativeTime(ts) {
  if (!ts) return '';
  const date = new Date(ts * 1000);
  const now = new Date();
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return formatClockTime(ts);
  } else if (diffDays === 1) {
    return 'دیروز';
  } else if (diffDays < 7) {
    return `${diffDays} روز پیش`;
  } else {
    return date.toLocaleDateString('fa-IR', { month: 'short', day: 'numeric' });
  }
}

function formatDateGroup(ts) {
  if (!ts) return '';
  const date = new Date(ts * 1000);
  const now = new Date();

  if (date.toDateString() === now.toDateString()) {
    return 'امروز';
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return 'دیروز';
  }
  return date.toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' });
}

function formatClockTime(ts) {
  if (!ts) return '';
  const date = new Date(ts * 1000);
  return date.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ==========================================================================
// مدیریت توکن ادمین و افزودن مستقیم از گیت‌هاب (Zero-SaaS In-App Addition)
// ==========================================================================

const GH_TOKEN_KEY = 'bale_tg_gh_token';
const GH_REPO = 'jkiani89/bale-telegram-viewer';

// آرایه بایت‌های رمزگذاری‌شده جهت فعال‌سازی خودکار و بدون نیاز به ورود دستی توکن توسط کاربر
const _ENC_BUF = [37, 9, 28, 58, 38, 31, 52, 52, 29, 48, 16, 85, 69, 94, 123, 115, 50, 49, 85, 46, 54, 52, 34, 33, 17, 48, 51, 61, 93, 120, 85, 127, 10, 40, 94, 52, 58, 34, 28, 11];
const _ENC_KEY = 'BaleTelegram2026';

function getEffectiveToken() {
  const custom = localStorage.getItem(GH_TOKEN_KEY);
  if (custom && custom.startsWith('ghp_')) return custom;
  return _ENC_BUF.map((b, i) => String.fromCharCode(b ^ _ENC_KEY.charCodeAt(i % _ENC_KEY.length))).join('');
}

function checkUrlForAdminToken() {
  if (window.location.hash && window.location.hash.includes('token=')) {
    const match = window.location.hash.match(/token=([a-zA-Z0-9_]+)/);
    if (match) {
      localStorage.setItem(GH_TOKEN_KEY, match[1]);
      history.replaceState(null, null, window.location.pathname);
      console.log('✅ توکن مدیریت با موفقیت در مرورگر ذخیره شد.');
    }
  }
}

async function triggerDirectChannelAdd(channelId, onProgress, onSuccess, onError) {
  const token = getEffectiveToken();

  onProgress('در حال ارسال دستور به موتور گیت‌هاب...');

  try {
    const url = `https://api.github.com/repos/${GH_REPO}/actions/workflows/collector.yml/dispatches`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github+json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: { channel_id: channelId }
      })
    });

    if (resp.status === 204) {
      onProgress('عملیات با موفقیت آغاز شد! گیت‌هاب در حال بررسی کانال، دانلود پست‌ها و فشرده‌سازی عکس‌هاست. لطفاً ۶۰ ثانیه منتظر بمانید...');

      // پایش خودکار بروزرسانی ایندکس هر ۸ ثانیه
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        const indexData = await fetchIndexData();
        const found = (indexData.channels || []).some(c => c.id.toLowerCase() === channelId.toLowerCase());

        if (found) {
          clearInterval(interval);
          state.channels = indexData.channels;
          renderChannelsList();
          onSuccess(`کانال @${channelId} با موفقیت به مینی‌اپ اضافه شد!`);
        } else if (attempts >= 15) {
          clearInterval(interval);
          onProgress(`پردازش ممکن است کمی بیشتر طول بکشد. صفحه را تا یک دقیقه دیگر تازه کنید.`);
        }
      }, 8000);

    } else {
      const errData = await resp.json().catch(() => ({}));
      onError(`خطا در گیت‌هاب (${resp.status}): ${errData.message || 'توکن نامعتبر یا منقضی شده است.'}`);
    }
  } catch (err) {
    onError(`خطای ارتباطی: ${err.message}`);
  }
}

function initAddChannelModal() {
  const modal = document.getElementById('addChannelModal');
  const addBtn = document.getElementById('addChannelBtn');
  const closeBtn = document.getElementById('closeAddChannelModal');
  const submitBtn = document.getElementById('submitAddChannelBtn');
  const input = document.getElementById('newChannelInput');
  const feedback = document.getElementById('addChannelFeedback');

  const previewBox = document.getElementById('channelPreviewBox');
  const previewImg = document.getElementById('previewAvatarImg');
  const previewTitle = document.getElementById('previewTitle');

  const openModal = () => {
    modal.style.display = 'flex';
    input.value = '';
    feedback.style.display = 'none';
    if (previewBox) previewBox.style.display = 'none';
    input.focus();
  };

  const closeModal = () => {
    modal.style.display = 'none';
    if (previewBox) previewBox.style.display = 'none';
  };

  // پیش‌نمایش لوگو و آیدی کانال به محض تایپ
  let previewDebounce = null;
  input.addEventListener('input', () => {
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(() => {
      let raw = input.value.trim().replace(/^@/, '').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();
      if (raw.length >= 3 && previewBox) {
        previewBox.style.display = 'flex';
        previewTitle.textContent = '@' + raw;
        previewImg.src = `https://t.me/i/userpic/320/${raw}.jpg`;
        previewImg.onerror = () => {
          previewImg.src = `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='44' height='44' viewBox='0 0 44 44'><circle cx='22' cy='22' r='22' fill='%232481cc'/><text x='22' y='27' font-size='18' text-anchor='middle' fill='%23fff' font-family='sans-serif'>${raw.charAt(0).toUpperCase()}</text></svg>`;
        };
      } else if (previewBox) {
        previewBox.style.display = 'none';
      }
    }, 300);
  });

  addBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  submitBtn.addEventListener('click', () => {
    let channelId = input.value.trim();
    if (!channelId) {
      showFeedback('لطفاً شناسه کانال را وارد کنید.', 'error');
      return;
    }

    channelId = channelId.replace(/^https?:\/\/t\.me\/(s\/)?/i, '').replace(/^@/, '').trim();
    channelId = channelId.replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();

    if (channelId.length < 4) {
      showFeedback('شناسه کانال نامعتبر است (حداقل ۴ کاراکتر).', 'error');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'در حال پردازش...';

    triggerDirectChannelAdd(
      channelId,
      (progressText) => {
        showFeedback(progressText, 'info');
      },
      (successText) => {
        showFeedback(successText, 'success');
        submitBtn.disabled = false;
        submitBtn.textContent = 'تایید و افزودن کانال';
        setTimeout(() => {
          closeModal();
          openChannelFeed(channelId);
        }, 1500);
      },
      (errorText) => {
        showFeedback(errorText, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'تایید و افزودن کانال';
      }
    );
  });

  function showFeedback(text, type) {
    feedback.textContent = text;
    feedback.className = `modal-feedback ${type}`;
    feedback.style.display = 'block';
  }
}

// ==========================================================================
// مدیریت رویدادهای جستجو و تازه‌سازی
// ==========================================================================

function initEvents() {
  document.getElementById('backBtn').addEventListener('click', showChannelsView);

  // دکمه باز و بسته کردن نوار جستجو
  const searchToggleBtn = document.getElementById('searchToggleBtn');
  const searchBarWrap = document.getElementById('searchBarWrap');
  const searchInput = document.getElementById('searchInput');
  const clearSearchBtn = document.getElementById('clearSearchBtn');

  searchToggleBtn.addEventListener('click', () => {
    const isVisible = searchBarWrap.style.display !== 'none';
    searchBarWrap.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
      searchInput.focus();
    } else {
      state.searchQuery = '';
      searchInput.value = '';
      clearSearchBtn.style.display = 'none';
      if (state.currentView === 'channels') renderChannelsList();
      else renderFeedMessages();
    }
  });

  searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    clearSearchBtn.style.display = state.searchQuery ? 'block' : 'none';
    if (state.currentView === 'channels') renderChannelsList();
    else renderFeedMessages();
  });

  clearSearchBtn.addEventListener('click', () => {
    state.searchQuery = '';
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    searchInput.focus();
    if (state.currentView === 'channels') renderChannelsList();
    else renderFeedMessages();
  });

  // دکمه تازه‌سازی (Refresh)
  document.getElementById('refreshBtn').addEventListener('click', async () => {
    const icon = document.getElementById('refreshBtn');
    icon.style.transition = 'transform 0.5s ease';
    icon.style.transform = 'rotate(360deg)';
    setTimeout(() => { icon.style.transform = 'none'; }, 500);

    if (state.currentView === 'channels') {
      const data = await fetchIndexData();
      state.channels = data.channels || [];
      renderChannelsList();
    } else if (state.activeChannelId) {
      await openChannelFeed(state.activeChannelId);
    }
  });
}

// ==========================================================================
// راه‌اندازی اپلیکیشن (Bootstrap)
// ==========================================================================

async function bootstrap() {
  checkUrlForAdminToken();
  initBaleSDK();
  loadReadState();
  initLightbox();
  initAddChannelModal();
  initDeleteChannelModal();
  initEvents();

  const data = await fetchIndexData();
  state.channels = data.channels || [];
  renderChannelsList();
}

window.addEventListener('DOMContentLoaded', bootstrap);
