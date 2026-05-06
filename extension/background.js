const SERVER = "http://localhost:8000";

async function checkUrl(url) {
  try {
    const res = await fetch(`${SERVER}/session/check?url=${encodeURIComponent(url)}`);
    const data = await res.json();
    return data.allowed;
  } catch {
    return true; // fail-open — if server is down, don't block
  }
}

async function sendEvent(url, title, content) {
  try {
    await fetch(`${SERVER}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        title,
        timestamp: Date.now() / 1000,
        meta_description: content?.meta || null,
        headings: content?.headings || null,
        body_snippet: content?.bodySnippet || null,
      }),
    });
  } catch {}
}

// Content script sends page content once the page is idle; forward it as an event
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type !== "PAGE_EVENT" || !sender.tab) return;
  const { url, title } = sender.tab;
  if (!url?.startsWith("http") || url.startsWith(SERVER)) return;
  sendEvent(url, title, msg.data);
});

// Block disallowed navigations before the page loads (focus mode)
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return; // main frame only
  const url = details.url;
  if (!url.startsWith("http") || url.startsWith(SERVER)) return;

  const allowed = await checkUrl(url);
  if (!allowed) {
    chrome.tabs.update(details.tabId, {
      url: `${SERVER}/blocked?url=${encodeURIComponent(url)}`,
    });
  }
});

// Send a lightweight event (no page content) on tab switch
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  if (!tab.url?.startsWith("http") || tab.url.startsWith(SERVER)) return;
  sendEvent(tab.url, tab.title, null);
});
