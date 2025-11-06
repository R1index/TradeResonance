(function () {
  const root = document.documentElement;

  function setTheme(theme) {
    root.classList.toggle('dark', theme === 'dark');
    root.dataset.theme = theme;
    try {
      localStorage.setItem('tr-theme', theme);
    } catch (err) {
      console.warn('Could not persist theme', err);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const next = root.classList.contains('dark') ? 'light' : 'dark';
        setTheme(next);
      });
    }

    const drawerBtn = document.querySelector('[data-drawer-toggle]');
    const drawer = document.getElementById('mobile-drawer');
    if (drawerBtn && drawer) {
      drawerBtn.addEventListener('click', () => {
        const expanded = drawerBtn.getAttribute('aria-expanded') === 'true';
        drawerBtn.setAttribute('aria-expanded', String(!expanded));
        drawer.classList.toggle('hidden', expanded);
      });
    }

    hydrateFlashMessages();
    startClocks();
  });

  function hydrateFlashMessages() {
    const flashNode = document.getElementById('flash-data');
    if (!flashNode) return;
    let flashes = [];
    try {
      flashes = JSON.parse(flashNode.dataset.flashes || '[]');
    } catch (err) {
      console.warn('Failed to parse flashes', err);
    }
    flashNode.remove();
    flashes.forEach((item) => toast(item[1] || item));
  }

  function toast(message, type = 'info') {
    if (!message) return;
    const container = document.getElementById('toast-root');
    if (!container) return;
    const el = document.createElement('div');
    el.role = 'status';
    el.textContent = message;
    if (type === 'error') {
      el.style.borderColor = 'var(--danger-bg)';
    }
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add('opacity-0', 'translate-x-4');
      setTimeout(() => el.remove(), 250);
    }, 4200);
  }

  function startClocks() {
    const utcEl = document.getElementById('clock-utc');
    const localEl = document.getElementById('clock-local');
    const tzEl = document.getElementById('clock-tz');
    if (!utcEl || !localEl || !tzEl) return;

    const update = () => {
      const now = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      const utcHours = pad(now.getUTCHours());
      const utcMinutes = pad(now.getUTCMinutes());
      const utcSeconds = pad(now.getUTCSeconds());
      utcEl.textContent = `${utcHours}:${utcMinutes}:${utcSeconds}`;

      const localHours = pad(now.getHours());
      const localMinutes = pad(now.getMinutes());
      const localSeconds = pad(now.getSeconds());
      localEl.textContent = `${localHours}:${localMinutes}:${localSeconds}`;
      tzEl.textContent = Intl.DateTimeFormat().resolvedOptions().timeZone.toUpperCase();

      const mUtc = document.getElementById('mClockUTC');
      const mLocal = document.getElementById('mClockLocal');
      const mTz = document.getElementById('mClockLocalTz');
      if (mUtc) mUtc.textContent = utcEl.textContent;
      if (mLocal) mLocal.textContent = localEl.textContent;
      if (mTz) mTz.textContent = tzEl.textContent;
    };

    update();
    setInterval(update, 1000);
  }

  if (window.htmx) {
    document.body.addEventListener('htmx:afterSwap', (event) => {
      if (event.target && event.target.id === 'tab-panel') {
        hydrateFlashMessages();
      }
    });

    document.body.addEventListener('htmx:responseError', () => {
      toast('Request failed', 'error');
    });
  }
})();
