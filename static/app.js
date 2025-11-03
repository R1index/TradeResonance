// app.js
// Lightweight enhancements: page transitions, Bootstrap toasts, tooltips, and theme sync.

document.addEventListener('DOMContentLoaded', () => {
  // Page enter animation
  document.body.classList.add('page-enter');
  requestAnimationFrame(() => {
    document.body.classList.add('page-enter-active');
  });

  // Bootstrap tooltips (if any)
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(el => new bootstrap.Tooltip(el));

  // Toast helper: show success/info/error
  window.notify = (msg, type = 'info') => {
    const toastZone = document.getElementById('toast-zone');
    const el = document.createElement('div');
    el.className = 'toast align-items-center text-bg-' + (type === 'success' ? 'success' : type === 'error' ? 'danger' : 'primary') + ' border-0';
    el.role = 'alert';
    el.ariaLive = 'assertive';
    el.ariaAtomic = 'true';
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>`;
    toastZone.appendChild(el);
    const t = new bootstrap.Toast(el, { delay: 2500 });
    t.show();
  };

  // Show flash message if present in data-flash attr
  const flash = document.querySelector('[data-flash]');
  if (flash && flash.dataset.flash) {
    try {
      const payload = JSON.parse(flash.dataset.flash);
      if (payload.message) {
        notify(payload.message, payload.type || 'info');
      }
    } catch(_) {}
  }
});
