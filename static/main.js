
(function(){
  function makeSmartDatalist(inputId, datalistId){
    const inp = document.getElementById(inputId);
    const dl  = document.getElementById(datalistId);
    if(!inp || !dl) return;

    const all = Array.from(dl.querySelectorAll('option')).map(o => o.value);
    function rebuild(prefix){
      const p = (prefix || "").toLowerCase();
      const pref = [], cont = [];
      for(const v of all){
        (v.toLowerCase().startsWith(p) ? pref : cont).push(v);
      }
      const merged = [...pref, ...cont].slice(0, 150);
      dl.innerHTML = merged.map(v => `<option value="${v}">`).join('');
    }
    inp.addEventListener('input', () => rebuild(inp.value));
    rebuild('');
  }
  makeSmartDatalist('cityInput', 'citiesList');
  makeSmartDatalist('productInput', 'productsList');
})();
