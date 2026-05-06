const SERVER = "http://localhost:8000";

async function checkUrl(url) {
  try {
    const res = await fetch(`${SERVER}/session/check?url=${encodeURIComponent(url)}`);
    const data = await res.json();
    return data.allowed;
  } catch {
    return true; // fail open — if server is down, don't block
  }
}

async function sendEvent(url, title) {
  try {
    await fetch(`${SERVER}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, timestamp: Date.now() / 1000 }),
    });
  } catch {}
}

// webNavigation fires on every navigation before the page loads — more reliable than onUpdated
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return; // main frame only, ignore iframes
  const url = details.url;
  if (!url.startsWith("http") || url.startsWith(SERVER)) return;

  const allowed = await checkUrl(url);
  if (!allowed) {
    chrome.tabs.update(details.tabId, {
      url: `${SERVER}/blocked?url=${encodeURIComponent(url)}`,
    });
  }
});

// Track active tab switches for nudge mode
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  if (tab.url && tab.url.startsWith("http")) {
    sendEvent(tab.url, tab.title);
  }
});
