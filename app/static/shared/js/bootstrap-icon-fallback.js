(function () {
  const ICON_MAP = {
    'bi-arrow-repeat': '↻',
    'bi-award': '🏆',
    'bi-bell': '🔔',
    'bi-box-arrow-in-right': '⇢',
    'bi-box-arrow-right': '⇠',
    'bi-broadcast-pin': '📡',
    'bi-bullseye': '◎',
    'bi-cart-check-fill': '🛒',
    'bi-cash-coin': '💰',
    'bi-chevron-down': '⌄',
    'bi-circle': '●',
    'bi-clipboard-data': '📋',
    'bi-clock-history': '🕘',
    'bi-cloud-arrow-up': '☁',
    'bi-collection-play': '🎬',
    'bi-envelope': '✉',
    'bi-eye': '◉',
    'bi-eye-slash': '⊘',
    'bi-folder2-open': '📂',
    'bi-globe-central-south-asia': '🌐',
    'bi-graph-up-arrow': '📈',
    'bi-grid-1x2-fill': '▦',
    'bi-images': '🖼',
    'bi-journal-check': '📘',
    'bi-journal-richtext': '📚',
    'bi-key': '🔑',
    'bi-layout-text-sidebar-reverse': '▤',
    'bi-layout-text-window-reverse': '▣',
    'bi-lightbulb': '💡',
    'bi-list': '☰',
    'bi-mortarboard': '🎓',
    'bi-mortarboard-fill': '🎓',
    'bi-palette2': '🎨',
    'bi-patch-question': '?',
    'bi-people': '👥',
    'bi-people-fill': '👥',
    'bi-person': '👤',
    'bi-person-badge': '🪪',
    'bi-person-badge-fill': '🪪',
    'bi-person-circle': '👤',
    'bi-play-fill': '▶',
    'bi-plug-fill': '🔌',
    'bi-plus-lg': '+',
    'bi-search': '⌕',
    'bi-search-heart': '♡',
    'bi-shield-check': '🛡',
    'bi-shield-lock': '🔒',
    'bi-sliders2': '⚙',
    'bi-speedometer2': '⏱',
    'bi-ticket-perforated': '🎫',
    'bi-translate': '文',
    'bi-upload': '⬆',
    'bi-volume-mute': '🔇',
    'bi-volume-up': '🔊',
    'bi-window-sidebar': '🗔',
    'bi-window-stack': '🗐'
  };

  function hasBootstrapIcons() {
    if (!document.fonts || !document.fonts.check) return false;
    try {
      return document.fonts.check('16px "bootstrap-icons"');
    } catch (e) {
      return false;
    }
  }

  function getFallback(classList) {
    for (const cls of classList) {
      if (ICON_MAP[cls]) return ICON_MAP[cls];
    }
    return '•';
  }

  function applyFallback() {
    document.documentElement.classList.add('bi-fallback-active');
    document.querySelectorAll('.bi').forEach((el) => {
      if (!el.dataset.fallback) {
        el.dataset.fallback = getFallback(el.classList);
      }
      el.setAttribute('aria-hidden', 'true');
    });
  }

  function init() {
    if (hasBootstrapIcons()) return;
    applyFallback();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(init).catch(init);
      } else {
        init();
      }
    });
  } else {
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(init).catch(init);
    } else {
      init();
    }
  }
})();
