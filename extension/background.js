const BASE_API = "http://127.0.0.1:8765";
const HEALTH_API = `${BASE_API}/health`;
const DOWNLOAD_API = `${BASE_API}/download`;

function collectMediaFromPage() {
  const urls = new Set();

  const add = (value) => {
    if (!value || typeof value !== "string") return;
    try {
      const absolute = new URL(value, location.href).href;
      if (/^https?:\/\//i.test(absolute)) urls.add(absolute);
    } catch (_) {}
  };

  document.querySelectorAll("video, audio").forEach((el) => {
    add(el.currentSrc);
    add(el.src);
    add(el.getAttribute("data-src"));
    add(el.getAttribute("data-url"));

    el.querySelectorAll("source").forEach((source) => {
      add(source.src || source.getAttribute("src"));
    });
  });

  document.querySelectorAll("img").forEach((el) => {
    add(el.currentSrc);
    add(el.src);
    add(el.getAttribute("data-src"));
    add(el.getAttribute("data-original"));
    add(el.getAttribute("data-lazy-src"));

    const srcset = el.getAttribute("srcset") || el.getAttribute("data-srcset");
    if (srcset) {
      srcset.split(",").forEach((part) => {
        add(part.trim().split(/\s+/)[0]);
      });
    }
  });

  document.querySelectorAll("source").forEach((el) => {
    add(el.src || el.getAttribute("src"));
    const srcset = el.getAttribute("srcset");
    if (srcset) {
      srcset.split(",").forEach((part) => {
        add(part.trim().split(/\s+/)[0]);
      });
    }
  });

  document.querySelectorAll(
    "meta[property='og:video'], " +
    "meta[property='og:video:url'], " +
    "meta[property='og:video:secure_url'], " +
    "meta[property='og:audio'], " +
    "meta[property='og:audio:url'], " +
    "meta[property='og:audio:secure_url'], " +
    "meta[name='twitter:player:stream'], " +
    "meta[property='og:image'], " +
    "meta[name='twitter:image']"
  ).forEach((el) => add(el.content));

  if (globalThis.performance?.getEntriesByType) {
    performance.getEntriesByType("resource").forEach((entry) => {
      if (
        /\.(mp4|webm|mkv|mov|m4v|avi|ts|mp3|m4a|aac|ogg|opus|wav|flac|m3u8|mpd|jpg|jpeg|png|webp|gif|avif)(\?|$)/i.test(
          entry.name
        )
      ) {
        add(entry.name);
      }
    });
  }

  return Array.from(urls).slice(0, 100);
}

async function setBadge(tabId, text) {
  await chrome.action.setBadgeText({ text, tabId });
  setTimeout(
    () => chrome.action.setBadgeText({ text: "", tabId }),
    2200
  );
}

async function getSessionToken() {
  const response = await fetch(HEALTH_API, {
    method: "GET",
    headers: {
      "X-MediaGrab-Client": "extension",
    },
  });
  if (!response.ok) {
    throw new Error(`Health HTTP ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.session_token) {
    throw new Error("MediaGrab session token unavailable");
  }
  return payload.session_token;
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id || !tab.url || !/^https?:\/\//i.test(tab.url)) {
    if (tab.id) await setBadge(tab.id, "!");
    return;
  }

  try {
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: collectMediaFromPage,
    });

    const candidates = injected?.[0]?.result || [];
    const sessionToken = await getSessionToken();

    const response = await fetch(DOWNLOAD_API, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-MediaGrab-Client": "extension",
        "X-MediaGrab-Token": sessionToken,
      },
      body: JSON.stringify({
        url: tab.url,
        candidates,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    await setBadge(tab.id, "OK");
  } catch (error) {
    console.error(
      "MediaGrab non raggiungibile o pagina non analizzabile",
      error
    );
    await setBadge(tab.id, "OFF");
  }
});
