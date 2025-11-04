// Тема
(function(){
  const btn = document.getElementById('themeToggle');
  function setTheme(next){
    const root = document.documentElement;
    if (next === 'dark') root.classList.add('dark'); else root.classList.remove('dark');
    localStorage.setItem('theme', next);
    let m = document.querySelector('meta[name="color-scheme"]');
    if (!m) { m = document.createElement('meta'); m.name = 'color-scheme'; document.head.appendChild(m); }
    m.content = next === 'dark' ? 'dark light' : 'light dark';
  }
  btn && btn.addEventListener('click', (e)=>{
    e.preventDefault();
    setTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark');
  });
})();

// Мобильное меню
(function(){
  const menuBtn = document.getElementById('menuBtn');
  const mobile = document.getElementById('mobileMenu');
  if (!menuBtn || !mobile) return;
  menuBtn.addEventListener('click', (e)=>{
    e.preventDefault();
    mobile.classList.toggle('hidden');
    const expanded = menuBtn.getAttribute('aria-expanded') === 'true';
    menuBtn.setAttribute('aria-expanded', (!expanded).toString());
  }, { passive:false });
})();

// Часы (UTC + local)
(function(){
  function fmt(dt){
    const y=dt.getFullYear(), m=String(dt.getMonth()+1).padStart(2,'0'), d=String(dt.getDate()).padStart(2,'0');
    const hh=String(dt.getHours()).padStart(2,'0'), mm=String(dt.getMinutes()).padStart(2,'0'), ss=String(dt.getSeconds()).padStart(2,'0');
    return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
  }
  function tzAbbr(timeZone){
    try{
      const f=new Intl.DateTimeFormat([], { timeZone, timeZoneName:'short' });
      const p=f.formatToParts(new Date()).find(x=>x.type==='timeZoneName');
      return p ? p.value : timeZone;
    }catch{ return timeZone; }
  }
  const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';
  const localLabel = tzAbbr(localTz);

  const elUTC=document.getElementById('clockUTC');
  const elLocal=document.getElementById('clockLocal');
  const elLocalTz=document.getElementById('clockLocalTz');
  const mUTC=document.getElementById('mClockUTC');
  const mLocal=document.getElementById('mClockLocal');
  const mLocalTz=document.getElementById('mClockLocalTz');
  if (elLocalTz) elLocalTz.textContent = localLabel;
  if (mLocalTz) mLocalTz.textContent = localLabel;

  function tick(){
    const now=new Date();
    const utc=new Date(now.getTime()+now.getTimezoneOffset()*60000);
    if (elUTC) elUTC.textContent=fmt(utc);
    if (elLocal) elLocal.textContent=fmt(now);
    if (mUTC) mUTC.textContent=fmt(utc);
    if (mLocal) mLocal.textContent=fmt(now);
  }
  tick();
  setInterval(tick,1000);
})();

// Тост из Flask flash()
(function(){
  const holder = document.querySelector('[data-flash]');
  if (!holder || !holder.dataset.flash) return;
  try{
    const {message, type} = JSON.parse(holder.dataset.flash);
    if (!message) return;
    const zone = document.getElementById('toast-zone');
    const d = document.createElement('div');
    d.className = 'card px-4 py-3 text-sm';
    d.textContent = message;
    zone.appendChild(d);
    setTimeout(()=>d.remove(), 3000);
  } catch {}
})();
