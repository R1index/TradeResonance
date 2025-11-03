// tw-app.js
(function(){
  const mobileMenu = document.getElementById('mobileMenu');
  const menuBtn = document.getElementById('menuBtn');
  if (menuBtn) menuBtn.addEventListener('click', () => mobileMenu.classList.toggle('hidden'));

  const toggle = document.getElementById('themeToggle');
  if (toggle) toggle.addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  });

  // Toasts
  const toastZone = document.getElementById('toast-zone');
  window.toast = (msg, type='info') => {
    const colors = { success: 'bg-emerald-600', error: 'bg-rose-600', info: 'bg-blue-600' };
    const el = document.createElement('div');
    el.className = `${colors[type]||colors.info} text-white rounded-xl shadow-soft px-4 py-2 animate-fade`;
    el.textContent = msg;
    toastZone.appendChild(el);
    setTimeout(()=> el.remove(), 2500);
  };

  const carrier = document.querySelector('[data-flash]');
  if (carrier && carrier.dataset.flash) {
    try {
      const payload = JSON.parse(carrier.dataset.flash);
      if (payload.message) toast(payload.message, payload.type || 'success');
    } catch(_) {}
  }
})();
