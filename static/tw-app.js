(function(){
  // Mobile menu only (theme handled in base.html)
  const menuBtn = document.getElementById('menuBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', (e) => {
      e.preventDefault();
      mobileMenu.classList.toggle('hidden');
      const expanded = menuBtn.getAttribute('aria-expanded') === 'true';
      menuBtn.setAttribute('aria-expanded', (!expanded).toString());
    }, { passive: false });
  }

  // Simple toast from flash
  const zone = document.getElementById('toast-zone');
  const carrier = document.querySelector('[data-flash]');
  function toast(msg){
    if(!msg || !zone) return;
    const el=document.createElement('div');
    el.className='rounded-xl px-4 py-2 bg-blue-600 text-white shadow';
    el.textContent=msg;
    zone.appendChild(el);
    setTimeout(()=>el.remove(), 2600);
  }
  try{
    if (carrier && carrier.dataset.flash) {
      const p = JSON.parse(carrier.dataset.flash);
      if (p && p.message) toast(p.message);
    }
  }catch(_){}
})();
