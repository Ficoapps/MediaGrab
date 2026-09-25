const API = "http://127.0.0.1:8765/download";

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

  if (performance && performance.getEntriesByType) {
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

  return Array.from(urls).slice(0, 300);
}

async function setBadge(tabId, text) {
  await chrome.action.setBadgeText({ text, tabId });
  setTimeout(
    () => chrome.action.setBadgeText({ text: "", tabId }),
    2200
  );
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

    const response = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: tab.url,
        candidates,
      }),
    });

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
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
