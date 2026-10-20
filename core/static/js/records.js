var state={page:1,search:'',category:'',status:'',sort:'-created_at'};
function qs(o){return Object.keys(o).map(k=>encodeURIComponent(k)+'='+encodeURIComponent(o[k])).join('&')}
function refreshIcons(){if(window.lucide&&lucide.createIcons)lucide.createIcons()}
function skeleton(){
  var h='';for(var i=0;i<5;i++)h+='<tr><td><div class="skel" style="width:60%"></div></td><td><div class="skel" style="width:30px"></div></td><td><div class="skel" style="width:70px"></div></td><td><div class="skel" style="width:80px"></div></td><td><div class="skel" style="width:80px"></div></td><td><div class="skel" style="width:80px"></div></td><td><div class="skel" style="width:140px"></div></td></tr>';
  return h;
}
async function load(){
  var tb=document.getElementById('rows');if(!tb)return;var pg=document.getElementById('pager');
  tb.innerHTML=skeleton();
  try{
    var j=await api('/api/records/?'+qs(state));
    if(!j.results.length){tb.innerHTML='<tr><td colspan="7"><div class="empty"><h3>No records found</h3><p>Try a different search or create a new record.</p><p><button class="btn sm" onclick="openAdd()">Add Record</button></p></div></td></tr>'}
    else tb.innerHTML=j.results.map(function(r){
      return '<tr><td>'+escapeHtml(r.name)+'</td><td>'+r.id+'</td><td>'+escapeHtml(r.category)+'</td><td><span class="badge b-info">'+escapeHtml(r.status_display)+'</span></td><td>'+(r.due_date||'—')+'</td><td>'+(r.created||'').slice(0,10)+'</td><td style="white-space:nowrap"><button class="btn ghost sm" onclick="openView('+r.id+')" aria-label="View record '+r.id+'">View</button> <button class="btn ghost sm" onclick="openEdit('+r.id+')" aria-label="Edit record '+r.id+'" title="Edit"><i data-lucide="pencil"></i></button> <button class="btn danger sm" onclick="askDelete('+r.id+')" aria-label="Delete record '+r.id+'" title="Delete"><i data-lucide="trash-2"></i></button></td></tr>'
    }).join('');
    pg.innerHTML='Page '+j.page+' of '+j.pages+' ('+j.total+' total) <button class="btn ghost sm" '+(j.page<=1?'disabled':'')+' onclick="go('+(j.page-1)+')" aria-label="Previous page">Prev</button> <button class="btn ghost sm" '+(j.page>=j.pages?'disabled':'')+' onclick="go('+(j.page+1)+')" aria-label="Next page">Next</button>';
    refreshIcons();
  }catch(e){tb.innerHTML='<tr><td colspan="7"><div class="empty"><h3>Could not load records</h3><p>'+escapeHtml(e.message)+'</p><p><button class="btn ghost sm" onclick="load()">Retry</button></p></div></td></tr>';toast(e.message,true)}
}
function escapeHtml(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function go(p){state.page=p;load()}
function onSearch(v){state.search=v;state.page=1;load()}
function onFilter(){state.category=document.getElementById('f-cat').value;state.status=document.getElementById('f-status').value;state.page=1;load()}
function onSort(f){var m={'name':'name','status':'status','date':'due_date'};var k=m[f]||f;state.sort=(state.sort===k?'-'+k:k);load()}
function openModal(){$('modal').classList.add('open');setTimeout(function(){var f=$('f-name');if(f)f.focus()},50)}
function closeModal(){var a=$('modal'),b=$('del-modal');if(a)a.classList.remove('open');if(b)b.classList.remove('open')}
function $(id){return document.getElementById(id)}
function openAdd(){$('m-title').textContent='Add Record';$('f-id').value='';$('f-name').value='';$('f-desc').value='';$('f-due').value='';$('f-prio').value='normal';$('f-status2').value='pending';$('e-name').hidden=true;openModal()}
async function openView(id){try{var j=await api('/api/records/'+id+'/');toast(j.record.name+' · '+j.record.status_display)}catch(e){toast(e.message,true)}}
async function openEdit(id){try{var j=await api('/api/records/'+id+'/');var r=j.record;$('m-title').textContent='Edit Record #'+r.id;$('f-id').value=r.id;$('f-name').value=r.name;$('f-desc').value=r.description;$('f-due').value=r.due_date||'';$('f-prio').value=r.priority;$('f-status2').value=r.status;$('f-cat2').value=r.category_id||'';$('e-name').hidden=true;openModal()}catch(e){toast(e.message,true)}}
function askDelete(id){$('del-id').value=id;$('del-modal').classList.add('open');setTimeout(function(){var b=document.querySelector('#del-modal .btn.danger');if(b)b.focus()},50)}
async function doDelete(){var id=$('del-id').value;try{await api('/api/records/'+id+'/',{method:'DELETE'});closeModal();toast('Record deleted');load()}catch(e){toast(e.message,true)}}
async function saveForm(ev){ev.preventDefault();var name=$('f-name').value.trim();$('e-name').hidden=!(name.length<3);if(name.length<3){$('f-name').focus();toast('Record name must be at least 3 characters',true);return}
  var id=$('f-id').value;var body={title:name,description:$('f-desc').value,unit:$('f-cat2').value||null,assignee:null,due_date:$('f-due').value,priority:$('f-prio').value,status:$('f-status2').value};
  if(!body.due_date){toast('Due date is required',true);$('f-due').focus();return}
  var btns=document.querySelectorAll('#modal .btn');btns.forEach(function(b){b.disabled=true});
  try{if(id){await api('/api/records/'+id+'/',{method:'PUT',body:JSON.stringify(body)});toast('Record updated')}else{await api('/api/records/',{method:'POST',body:JSON.stringify(body)});toast('Record created')}closeModal();load()}catch(e){toast(e.message,true)}finally{btns.forEach(function(b){b.disabled=false})}}
document.addEventListener('DOMContentLoaded',function(){
  try{
    var u=new URLSearchParams(window.location.search);var s=u.get('search')||'';
    if(s){state.search=s;var q=document.getElementById('q');if(q)q.value=s;var top=document.getElementById('top-search');if(top)top.value=s}
  }catch(e){}
  load();
  document.querySelectorAll('.modal').forEach(function(m){
    m.addEventListener('click',function(e){if(e.target===m)closeModal()});
  });
});
