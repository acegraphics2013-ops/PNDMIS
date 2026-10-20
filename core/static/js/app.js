function toast(msg, isErr){
  var w=document.getElementById('toasts');if(!w)return;
  var d=document.createElement('div');d.setAttribute('role','status');
  if(isErr)d.className='err';
  var ic=document.createElement('span');ic.className='t-ic';ic.textContent=isErr?'\u26A0':'\u2713';
  var t=document.createElement('span');t.textContent=msg;
  var x=document.createElement('button');x.className='t-x';x.setAttribute('aria-label','Dismiss');x.textContent='\u00D7';
  x.onclick=function(){d.remove()};
  d.appendChild(ic);d.appendChild(t);d.appendChild(x);w.appendChild(d);
  if(window.lucide&&lucide.createIcons)lucide.createIcons();
  setTimeout(function(){if(d.parentNode)d.remove()},4000);
}
function toggleSidebar(){
  var s=document.getElementById('sidebar');if(!s)return;
  s.classList.toggle('open');
  try{if(window.innerWidth<=900)sessionStorage.setItem('pndmis-mob',s.classList.contains('open')?'1':'0')}catch(e){}
}
function toggleCollapse(){
  var c=document.body.classList.toggle('nav-collapsed');
  try{localStorage.setItem('pndmis-collapsed',c?'1':'0')}catch(e){}
}
function closeMenus(){['pmenu','notif-menu'].forEach(function(id){var m=document.getElementById(id);if(m)m.classList.remove('open')})}
function toggleMenu(id){
  var m=document.getElementById(id);if(!m)return;
  var was=m.classList.contains('open');closeMenus();
  if(!was)m.classList.add('open');
  if(id==='notif-menu'&&!was)loadNotifs();
}
async function loadNotifs(){
  var box=document.getElementById('notif-body');if(!box)return;
  box.innerHTML='<div class="meta" style="padding:8px 0"><span class="spin"></span> Loading…</div>';
  try{
    var s=await api('/api/stats/');
    box.innerHTML='<a href="/tasks/?filter=overdue">Overdue items: <b>'+s.overdue+'</b></a>'
      +'<a href="/deliverables/?overdue=1">Pending requirements: <b>'+s.pending_records+'</b></a>'
      +'<a href="/records/">Total records: <b>'+s.total_records+'</b></a>';
  }catch(e){box.innerHTML='<div class="meta" style="padding:8px 0">Could not load notifications.</div>'}
}
function tickPH(){var el=document.getElementById('ph-clock');if(!el)return;try{el.textContent=new Date().toLocaleString('en-PH',{timeZone:'Asia/Manila',weekday:'short',year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'})}catch(e){}}
setInterval(tickPH,1000);
function getCookie(n){var m=document.cookie.match('(^|;)\\s*'+n+'\\s*=\\s*([^;]+)');return m?m.pop():''}
async function api(path,opts){opts=opts||{};opts.headers=opts.headers||{};opts.headers['X-CSRFToken']=getCookie('csrftoken');opts.headers['Content-Type']='application/json';var r=await fetch(path,opts);var j=null;try{j=await r.json()}catch(e){}if(!r.ok)throw new Error((j&&j.error)||('HTTP '+r.status));return j}
function submitTopSearch(v){
  v=(v||'').trim();
  if(window.onSearch&&document.getElementById('rows')){window.onSearch(v);return}
  window.location.href='/records/?search='+encodeURIComponent(v);
}
document.addEventListener('DOMContentLoaded',function(){
  tickPH();
  try{
    if(localStorage.getItem('pndmis-collapsed')==='1')document.body.classList.add('nav-collapsed');
    if(window.innerWidth<=900&&sessionStorage.getItem('pndmis-mob')==='1')document.getElementById('sidebar').classList.add('open');
  }catch(e){}
  if(window.lucide&&lucide.createIcons)lucide.createIcons();
  document.addEventListener('click',function(e){
    if(!e.target.closest('.profile-wrap')&&!e.target.closest('#notif-wrap'))closeMenus();
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'){closeMenus();if(window.closeModal)closeModal();var s=document.getElementById('sidebar');if(s)s.classList.remove('open')}
    if(e.key==='/'&&!/input|textarea|select/i.test(document.activeElement.tagName)){e.preventDefault();var sbox=document.getElementById('top-search');if(sbox)sbox.focus()}
  });
  var ov=document.getElementById('overlay');
  if(ov)ov.addEventListener('click',function(){document.getElementById('sidebar').classList.remove('open')});
  document.querySelectorAll('.nav a').forEach(function(a){
    a.addEventListener('click',function(){if(window.innerWidth<=900)document.getElementById('sidebar').classList.remove('open')});
  });
  var openModalFn=window.openModal;
});
