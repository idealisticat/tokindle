const DEFAULT_BACKEND = 'http://127.0.0.1:8000';

document.getElementById('backend').placeholder = DEFAULT_BACKEND;
chrome.storage.local.get({ backendUrl: DEFAULT_BACKEND }, (o) => {
  document.getElementById('backend').value = o.backendUrl;
});

document.getElementById('save').addEventListener('click', () => {
  const url = document.getElementById('backend').value.trim() || DEFAULT_BACKEND;
  chrome.storage.local.set({ backendUrl: url }, () => {
    document.getElementById('backend').value = url;
    alert('Saved.');
  });
});
