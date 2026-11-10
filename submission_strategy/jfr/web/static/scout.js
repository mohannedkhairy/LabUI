(() => {
  const panel = document.querySelector('[data-scout-panel]');
  if (!panel) return;
  const full = panel.dataset.full === 'true';
  let timer;
  let previous = panel.querySelector('[data-status]')?.dataset.status;

  async function refresh() {
    clearTimeout(timer);
    try {
      const response = await fetch('/research/scout/widget' + (full ? '?full=true' : ''), {signal: AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error('Could not load publication scout (' + response.status + ').');
      panel.innerHTML = await response.text();
      const widget = panel.querySelector('[data-status]');
      if (full && previous === 'running' && widget.dataset.status !== 'running') {
        location.reload();
        return;
      }
      previous = widget.dataset.status;
      timer = setTimeout(refresh, widget.dataset.running === 'true' ? 5000 : 60000);
    } catch (error) {
      let message = panel.querySelector('[data-scout-error]');
      if (!message) {
        message = document.createElement('p');
        message.className = 'scout-error';
        message.dataset.scoutError = '';
        message.setAttribute('role', 'status');
        panel.appendChild(message);
      }
      message.textContent = 'Publication scout is unavailable. Retrying in one minute.';
      timer = setTimeout(refresh, 60000);
    }
  }

  panel.addEventListener('submit', async (event) => {
    if (!event.target.matches('[data-scout-run]')) return;
    event.preventDefault();
    const button = event.target.querySelector('button');
    button.disabled = true;
    button.textContent = 'Starting…';
    try {
      const response = await fetch('/api/scout/run', {method: 'POST', signal: AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error('Could not start the scan. Please try again.');
      previous = 'running';
      await refresh();
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Scan now';
      const message = document.createElement('p');
      message.className = 'scout-error';
      message.setAttribute('role', 'alert');
      message.textContent = error.message;
      panel.appendChild(message);
    }
  });
  refresh();
})();
