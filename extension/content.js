(function () {
  const meta = document.querySelector('meta[name="description"]')?.content || '';

  const headings = [...document.querySelectorAll('h1, h2')]
    .slice(0, 5)
    .map(h => h.textContent.trim())
    .filter(Boolean);

  // ~500 chars of visible body text; innerText respects CSS visibility
  const bodySnippet = (document.body?.innerText || '').slice(0, 500).trim();

  chrome.runtime.sendMessage({
    type: 'PAGE_EVENT',
    data: { meta, headings, bodySnippet },
  });
})();
