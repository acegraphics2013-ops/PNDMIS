document.addEventListener('DOMContentLoaded', async function(){
  try{
    var a = await api('/api/analytics/');
    var sctx = document.getElementById('ch-status');
    if(sctx && window.Chart){
      new Chart(sctx,{type:'doughnut',data:{labels:(a.by_status||[]).map(x=>x.status),datasets:[{data:(a.by_status||[]).map(x=>x.count),borderWidth:1}]},options:{responsive:false,maintainAspectRatio:false,cutout:'68%',plugins:{legend:{position:'bottom',labels:{boxWidth:8,boxHeight:8,font:{size:11},padding:8}}}}});
    }
    var uctx = document.getElementById('ch-unit');
    if(uctx && window.Chart){
      new Chart(uctx,{type:'bar',data:{labels:(a.by_unit||[]).map(x=>x.unit__name||'—'),datasets:[{label:'Active staff',data:(a.by_unit||[]).map(x=>x.count)}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0,font:{size:11}}},x:{ticks:{font:{size:11}}}}}});
    }
  }catch(e){ console.warn(e); }
});
