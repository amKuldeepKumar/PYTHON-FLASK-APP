
document.addEventListener('DOMContentLoaded', () => {
  const shell = document.getElementById('workspaceShell');
  if (!shell) return;

  const markLoading = (event) => {
    const target = event.target.closest('a, button[type="submit"]');
    if (!target) return;
    if (target.hasAttribute('data-no-loading')) return;
    if (target.tagName === 'A') {
      const href = target.getAttribute('href') || '';
      if (!href || href.startsWith('#') || target.target === '_blank' || target.hasAttribute('download')) return;
    }
    shell.classList.add('is-page-loading');
  };

  document.addEventListener('click', markLoading, true);
  window.addEventListener('pageshow', () => shell.classList.remove('is-page-loading'));
  window.addEventListener('beforeunload', () => shell.classList.add('is-page-loading'));
});
