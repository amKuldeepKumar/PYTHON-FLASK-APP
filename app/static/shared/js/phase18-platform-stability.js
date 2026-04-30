
// Phase 18 — Final Stability + Theme Pass
(function () {
  function lockSubmittingForms() {
    document.querySelectorAll('form').forEach(function (form) {
      if (form.dataset.phase18Bound === '1') return;
      form.dataset.phase18Bound = '1';
      form.addEventListener('submit', function () {
        window.setTimeout(function () {
          form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
            if (btn.disabled) return;
            btn.dataset.originalLabel = btn.innerHTML || btn.value || '';
            btn.disabled = true;
            if (btn.tagName === 'BUTTON') {
              btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Working...';
            } else {
              btn.value = 'Working...';
            }
          });
        }, 0);
      }, { once: true });
    });
  }

  function stabilisePlaceholderLinks() {
    document.querySelectorAll('a[href="#"]').forEach(function (anchor) {
      anchor.addEventListener('click', function (event) {
        event.preventDefault();
      });
    });
  }

  function restoreDisabledButtonsOnHistoryNavigation() {
    window.addEventListener('pageshow', function () {
      document.querySelectorAll('button[disabled][data-original-label], input[disabled][data-original-label]').forEach(function (btn) {
        btn.disabled = false;
        if (btn.tagName === 'BUTTON') {
          btn.innerHTML = btn.dataset.originalLabel;
        } else {
          btn.value = btn.dataset.originalLabel;
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    lockSubmittingForms();
    stabilisePlaceholderLinks();
    restoreDisabledButtonsOnHistoryNavigation();
  });
})();
