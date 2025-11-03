(function(){
  const mobileMenu = document.getElementById('mobileMenu');
  const menuBtn = document.getElementById('menuBtn');
  if (menuBtn) menuBtn.addEventListener('click', () => mobileMenu.classList.toggle('hidden'));
  const toggle = document.getElementById('themeToggle');
  if (toggle) toggle.addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  });
  const zone = document.getElementById('toast-zone');
  const carrier = document.querySelector('[data-flash]');
  function toast(msg){ if(!msg) return; const el=document.createElement('div'); el.className='rounded-xl px-4 py-2 bg-blue-600 text-white shadow'; el.textContent=msg; zone.appendChild(el); setTimeout(()=>el.remove(), 2600); }
  try{ if(carrier && carrier.dataset.flash){ const p=JSON.parse(carrier.dataset.flash); toast(p.message); } }catch(_){}
})();