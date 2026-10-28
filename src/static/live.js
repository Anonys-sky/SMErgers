// Live group: new messages arrive on their own, and the page updates itself. Display only:
// every decision (who may approve, what reaches the bill) is made on the server.
(function () {
  const bar = document.getElementById('live-bar');
  if (!bar) return;
  const status = document.getElementById('live-status');
  const toggle = document.getElementById('live-toggle');
  const form = document.getElementById('live-send');
  const every = Number(bar.dataset.interval) / 1000;
  let remaining = Number(bar.dataset.remaining), left = every, paused = false, busy = false;

  const region = () => document.getElementById('live-region');
  const typing = () => {
    const a = document.activeElement;
    return !!a && region().contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);
  };

  function render() {
    if (remaining === 0) status.textContent = 'Live group: all messages have arrived';
    else if (paused) status.textContent = 'Live group: paused. ' + remaining + ' message' + (remaining === 1 ? '' : 's') + ' still to arrive';
    else status.textContent = 'Live group: next message in ' + left + ' s. ' + remaining + ' still to arrive';
    toggle.hidden = remaining === 0;
    toggle.textContent = paused ? 'Resume' : 'Pause';
  }

  async function refresh() {
    const res = await fetch(location.pathname + location.search, {credentials: 'same-origin'});
    const next = new DOMParser().parseFromString(await res.text(), 'text/html').getElementById('live-region');
    if (!next || typing()) return;
    const knownChanges = new Set([...region().querySelectorAll('article.change')].map(c => c.id));
    const knownMessages = new Set([...region().querySelectorAll('.msg')].map(m => m.id).filter(Boolean));
    region().innerHTML = next.innerHTML;
    region().querySelectorAll('article.change').forEach(c => { if (!knownChanges.has(c.id)) c.classList.add('fresh'); });
    region().querySelectorAll('.msg').forEach(m => { if (m.id && !knownMessages.has(m.id)) m.classList.add('fresh'); });
    const chat = region().querySelector('.chat');
    if (chat) chat.scrollTop = chat.scrollHeight;
  }

  async function deliver() {
    busy = true;
    try {
      const res = await fetch(bar.dataset.next, {method: 'POST', headers: {'X-Requested-With': 'fetch'}, credentials: 'same-origin'});
      if (!res.ok) throw new Error('delivery failed');
      remaining = (await res.json()).remaining;
      await refresh();
    } catch (err) {
      paused = true;   // stop quietly; the buttons still work
    } finally {
      busy = false;
      render();
    }
  }

  toggle.addEventListener('click', () => { paused = !paused; left = every; render(); });
  // Someone is reading the evidence: stop moving things under them.
  region().addEventListener('click', e => { if (e.target.closest('.show-src, .msg.linked')) { paused = true; render(); } });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    busy = true;
    try {
      const res = await fetch(bar.dataset.send, {method: 'POST', body: new URLSearchParams(new FormData(form)),
        headers: {'X-Requested-With': 'fetch'}, credentials: 'same-origin'});
      const data = await res.json();
      if (!res.ok) { status.textContent = data.error || 'The message could not be sent.'; return; }
      form.elements.text.value = '';
      remaining = data.remaining;
      paused = true;   // the person typing is now driving; the recorded messages wait until Resume
      await refresh();
    } catch (err) {
      form.submit();   // no JavaScript path: a normal form post
    } finally {
      busy = false;
      render();
    }
  });

  setInterval(() => {
    if (paused || busy || remaining === 0) return;
    left -= 1;
    if (left <= 0) { left = every; deliver(); }
    render();
  }, 1000);
  render();
})();
