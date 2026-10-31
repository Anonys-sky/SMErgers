// Background ingestion runs on the server. This only updates the visible review.
(function () {
  const region = document.getElementById('live-region');
  const status = document.getElementById('bridge-status');
  const pending = document.getElementById('bridge-pending');
  let editing = false;
  region.addEventListener('input', () => { editing = true; });
  region.addEventListener('change', () => { editing = true; });
  region.addEventListener('click', e => {
    if (e.target.closest('.show-src, .msg.linked')) editing = true;
  });

  async function poll() {
    try {
      const response = await fetch(location.pathname + location.search, {cache: 'no-store'});
      if (!response.ok) throw new Error('Could not refresh');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = doc.getElementById('live-region');
      const nextStatus = doc.getElementById('bridge-status');
      if (nextStatus) status.textContent = nextStatus.textContent;
      if (!next || next.innerHTML === region.innerHTML) return;
      // Preserve unsaved form values and the evidence someone is reviewing.
      if (editing || region.contains(document.activeElement)) {
        pending.hidden = false;
        return;
      }
      const scrollTop = region.querySelector('.chat')?.scrollTop || 0;
      region.innerHTML = next.innerHTML;
      const chat = region.querySelector('.chat');
      if (chat) chat.scrollTop = scrollTop;
      pending.hidden = true;
    } catch (err) {
      status.textContent = 'Could not refresh this view. Retrying automatically.';
    } finally {
      setTimeout(poll, 4000);
    }
  }
  setTimeout(poll, 4000);
})();
