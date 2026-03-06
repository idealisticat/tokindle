const DEFAULT_BACKEND = 'http://127.0.0.1:8000';

function show(msg, isError = false) {
  const el = document.getElementById('result');
  el.textContent = msg;
  el.className = isError ? 'err' : 'ok';
  el.style.display = 'block';
}

function getBackendUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get({ backendUrl: DEFAULT_BACKEND }, (o) => resolve(o.backendUrl));
  });
}

document.getElementById('convert').addEventListener('click', async () => {
  const btn = document.getElementById('convert');
  btn.disabled = true;
  document.getElementById('result').style.display = 'none';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      show('No active tab.', true);
      return;
    }

    const [{ result: htmlResult }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({
        title: document.title || 'Untitled',
        html: document.documentElement.outerHTML,
      }),
    });

    if (!htmlResult?.html) {
      show('Could not read page (e.g. chrome://). Try a normal webpage.', true);
      return;
    }

    const backend = await getBackendUrl();
    const url = backend.replace(/\/$/, '') + '/parse-html';
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: htmlResult.title || 'Untitled',
        html_content: htmlResult.html,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      show(data.detail || `HTTP ${res.status}`, true);
      return;
    }
    if (data.success && data.path) {
      let msg = `Saved: ${data.path}\nTitle: ${data.title || '-'}`;
      if (data.email_sent) {
        msg += '\nSent to Kindle.';
      } else if (data.email_error) {
        msg += `\nEmail: ${data.email_error}`;
      }
      show(msg);
    } else {
      show(JSON.stringify(data), true);
    }
  } catch (e) {
    show(e.message || String(e), true);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('settings').addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});
