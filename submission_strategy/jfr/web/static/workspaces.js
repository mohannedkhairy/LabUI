(() => {
  const switcher = document.getElementById('workspace-switcher');
  if (!switcher) return;
  document.addEventListener('click', event => {
    if (switcher.open && !switcher.contains(event.target)) switcher.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && switcher.open) {
      switcher.open = false;
      switcher.querySelector('summary').focus();
    }
  });
})();
