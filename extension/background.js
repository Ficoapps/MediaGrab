const API = "http://127.0.0.1:8765/download";

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.url || !/^https?:\/\//i.test(tab.url)) {
    await chrome.action.setBadgeText({ text: "!", tabId: tab.id });
    return;
  }

  try {
    const response = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: tab.url })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await chrome.action.setBadgeText({ text: "OK", tabId: tab.id });
    setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 1800);
  } catch (error) {
    console.error("MediaGrab non raggiungibile", error);
    await chrome.action.setBadgeText({ text: "OFF", tabId: tab.id });
    setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 2500);
  }
});
