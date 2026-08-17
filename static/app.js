
document.addEventListener('DOMContentLoaded',()=>{
  const sidebar=document.getElementById('appSidebar'), overlay=document.getElementById('sidebarOverlay');
  const open=document.getElementById('sidebarOpen'), close=document.getElementById('sidebarClose');
  const setOpen=(v)=>{sidebar?.classList.toggle('open',v);overlay?.classList.toggle('open',v);document.body.classList.toggle('menu-open',v)};
  open?.addEventListener('click',()=>setOpen(true));close?.addEventListener('click',()=>setOpen(false));overlay?.addEventListener('click',()=>setOpen(false));
  document.querySelectorAll('.flash-close').forEach(btn=>btn.addEventListener('click',()=>btn.closest('.flash-message')?.remove()));
  document.querySelectorAll('.password-toggle').forEach(btn=>btn.addEventListener('click',()=>{
    const input=btn.parentElement.querySelector('input'); const icon=btn.querySelector('i');
    input.type=input.type==='password'?'text':'password'; icon.classList.toggle('bi-eye'); icon.classList.toggle('bi-eye-slash');
  }));
  const search=document.getElementById('tableSearch'), table=document.getElementById('searchTable');
  search?.addEventListener('input',()=>{
    const q=search.value.toLowerCase().trim();
    table?.querySelectorAll('tr').forEach(row=>row.style.display=row.innerText.toLowerCase().includes(q)?'':'none');
  });
  const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('is-visible');io.unobserve(e.target)}}),{threshold:.08});
  document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
});
