/* Two independent views of one PDF, with durable page-anchored review records. */
let pdfDoc=null, currentPid='', marks=[], notes=[], selected=null, tool='read', color='#f4d75e';
let undoStack=[], redoStack=[], saveTimer, saveChain=Promise.resolve(), dirty=false, editId=null, activeSide='L';
const $=id=>document.getElementById(id);
const API=pid=>'/api/rag/review/paper/'+encodeURIComponent(pid);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid=()=>crypto.randomUUID();
function toast(s){$('toast').textContent=s;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),2200);}
async function request(url,options){const r=await fetch(url,options);if(!r.ok)throw Error('Request failed ('+r.status+')');return r;}
function snapshot(){return structuredClone({marks,notes});}
function history(){undoStack.push(snapshot());undoStack=undoStack.slice(-50);redoStack=[];}
function changed(){dirty=true;redraw();renderRecords();clearTimeout(saveTimer);$('statusPill').textContent='Unsaved changes';saveTimer=setTimeout(()=>saveAll().catch(()=>{}),700);}
function restore(from,to){if(!from.length)return;to.push(snapshot());({marks,notes}=from.pop());changed();}
function undo(){restore(undoStack,redoStack);} function redo(){restore(redoStack,undoStack);}
function saveAll(){
 clearTimeout(saveTimer);if(!currentPid||!dirty)return saveChain;
 const pid=currentPid, data=snapshot();
 const operation=saveChain.catch(()=>{}).then(async()=>{
  for(const kind of ['marks','notes'])await request(API(pid)+'/'+kind+'/snapshot',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(pid===currentPid&&JSON.stringify(snapshot())===JSON.stringify(data)){dirty=false;$('statusPill').textContent='Saved';}
 });
 saveChain=operation;operation.catch(e=>{$('statusPill').textContent='Save failed — use Save to retry';toast(e.message);});return operation;
}
class PageView{
 constructor(side,number,owner){this.side=side;this.owner=owner;this.page=number;this.scale=1;this.canvas=$(side+'canvas');this.wrap=$(side+'wrap');this.svg=$(side+'over');this.viewer=owner.viewer;this.queue=Promise.resolve();
 this.wrap.addEventListener('pointerdown',e=>this.down(e));this.wrap.addEventListener('pointermove',e=>this.move(e));this.wrap.addEventListener('pointerup',e=>this.up(e));this.wrap.addEventListener('pointercancel',()=>{this.drag=null;this.overlay();});this.wrap.addEventListener('pointerdown',()=>{activeSide=owner.side;owner.page=this.page;owner.labels();});}
 num(p){if(!pdfDoc)return;this.page=Math.min(pdfDoc.numPages,Math.max(1,Number(p)));return this.render();}
 turn(d){return this.num(this.page+d);} zoom(d){this.scale=Math.min(3,Math.max(.35,this.scale+d));return this.render();}
 syncTo(side){return pane(side).num(this.page);}
 render(){const doc=pdfDoc,pg=this.page,scale=this.scale;if(!doc)return Promise.resolve();this.queue=this.queue.catch(()=>{}).then(async()=>{
 if(doc!==pdfDoc)return;const page=await doc.getPage(pg),vp=page.getViewport({scale}),ratio=devicePixelRatio||1;
 this.canvas.width=Math.floor(vp.width*ratio);this.canvas.height=Math.floor(vp.height*ratio);this.canvas.style.width=vp.width+'px';this.canvas.style.height=vp.height+'px';this.wrap.style.width=vp.width+'px';
 await page.render({canvasContext:this.canvas.getContext('2d'),viewport:vp,transform:[ratio,0,0,ratio,0,0]}).promise;
 const text=$(this.side+'text');text.replaceChildren();text.style.setProperty('--scale-factor',scale);
 await pdfjsLib.renderTextLayer({textContentSource:await page.getTextContent(),container:text,viewport:vp,textDivs:[]}).promise;
 this.vp=vp;this.drawnPage=pg;this.overlay();
 }).catch(e=>{toast('PDF render failed: '+e.message);});return this.queue;}
 overlay(){if(!this.vp)return;const W=this.vp.width,H=this.vp.height;this.svg.setAttribute('width',W);this.svg.setAttribute('height',H);this.svg.replaceChildren();
 for(const m of marks.filter(m=>m.page===this.drawnPage))for(const r of m.rects){const el=document.createElementNS('http://www.w3.org/2000/svg',m.type==='ellipse'?'ellipse':'rect');const x=r.x*W,y=(1-r.y-r.height)*H,w=r.width*W,h=r.height*H;
 const attrs=m.type==='ellipse'?{cx:x+w/2,cy:y+h/2,rx:w/2,ry:h/2}:{x,y,width:w,height:h};for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);el.setAttribute('fill',m.type==='highlight'?m.color+'66':'transparent');el.setAttribute('stroke',m.color);el.setAttribute('stroke-width',selected===m.id?3:1.5);el.style.pointerEvents=tool==='read'?'auto':'none';el.addEventListener('click',()=>selectMark(m.id));this.svg.append(el);}
 if(this.drag){const d=this.drag,el=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const[k,v]of Object.entries({x:Math.min(d.x,d.ex)*W,y:Math.min(d.y,d.ey)*H,width:Math.abs(d.ex-d.x)*W,height:Math.abs(d.ey-d.y)*H,fill:'transparent',stroke:color,'stroke-dasharray':'5 3'}))el.setAttribute(k,v);this.svg.append(el);}}
 point(e){const r=this.canvas.getBoundingClientRect();return{x:Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))};}
 down(e){if(!pdfDoc||!this.vp||tool==='read'||e.button!==0)return;e.preventDefault();this.wrap.setPointerCapture(e.pointerId);const p=this.point(e);this.drag={...p,ex:p.x,ey:p.y,page:this.drawnPage};}
 move(e){if(!this.drag)return;const p=this.point(e);Object.assign(this.drag,{ex:p.x,ey:p.y});this.overlay();}
 up(e){if(!this.drag)return;this.move(e);const d=this.drag;this.drag=null;this.overlay();const width=Math.abs(d.ex-d.x),height=Math.abs(d.ey-d.y);if(width<.01||height<.01)return;
 history();const figure=tool==='figure';const m={id:uid(),type:figure?'rectangle':tool,page:d.page,color,note:figure?'Figure caption: ': '',rects:[{x:Math.min(d.x,d.ex),y:1-Math.max(d.y,d.ey),width,height}]};marks.push(m);selected=m.id;changed();tab('marks');if(figure){const field=$('markList').querySelector('textarea[data-id="'+m.id+'"]');field?.focus();toast('Figure captured — write its caption');}}
}
class Pane {
 constructor(side){this.side=side;this.page=1;this.scale=1;this.viewer=$(side+'viewer');this.views=[];this.queue=Promise.resolve();this.generation=0;
  this.viewer.addEventListener('scroll',()=>this.trackPage(),{passive:true});this.viewer.addEventListener('pointerdown',()=>{activeSide=side;this.labels();});
 }
 labels(){if(!pdfDoc)return;$(this.side.toLowerCase()+'pNum').textContent=this.page+' / '+pdfDoc.numPages;$(this.side.toLowerCase()+'pZoom').textContent=Math.round(this.scale*100)+'%';if(activeSide===this.side)$('notePg').textContent=this.page;}
 trackPage(){const top=this.viewer.getBoundingClientRect().top+this.viewer.clientHeight*.25;let nearest=this.views[0];for(const v of this.views){if(v.wrap.getBoundingClientRect().top<=top)nearest=v;else break;}if(nearest){this.page=nearest.page;this.labels();}}
 num(p){if(!pdfDoc||!Number.isFinite(Number(p)))return;this.page=Math.min(pdfDoc.numPages,Math.max(1,Math.round(Number(p))));const v=this.views[this.page-1];if(v){this.viewer.scrollTop=Math.max(0,v.wrap.offsetTop-12);this.labels();return this.ensure(v);}}
 turn(d){return this.num(this.page+d);} syncTo(side){return pane(side).num(this.page);}
 zoom(d){this.scale=Math.min(3,Math.max(.35,this.scale+d));return this.render();}
 ensure(v){if(v.loaded)return v.queue;v.loaded=true;v.scale=this.scale;return v.render();}
 render(){const doc=pdfDoc,scale=this.scale,pg=this.page,generation=++this.generation;if(!doc)return Promise.resolve();this.observer?.disconnect();
 this.queue=Promise.all(this.views.map(v=>v.queue)).then(async()=>{
  if(doc!==pdfDoc||generation!==this.generation)return;
  this.viewer.replaceChildren();this.views=[];
  // Reserve every page's actual dimensions so lazy rendering never shifts text.
  for(let n=1;n<=doc.numPages;n++){
   const vp=(await doc.getPage(n)).getViewport({scale});if(doc!==pdfDoc||generation!==this.generation)return;
   const id=this.side+'-'+n,wrap=document.createElement('div');wrap.id=id+'wrap';wrap.className='page-wrap continuous-page';wrap.style.width=vp.width+'px';wrap.style.height=vp.height+'px';wrap.setAttribute('aria-label','Page '+n);
   wrap.innerHTML='<canvas id="'+id+'canvas"></canvas><div class="textLayer" id="'+id+'text"></div><svg id="'+id+'over" class="mark-layer"></svg>';
   this.viewer.append(wrap);const view=new PageView(id,n,this);view.viewer=this.viewer;view.scale=scale;view.wrap.style.touchAction=tool==='read'?'auto':'none';$(id+'text').style.pointerEvents=tool==='read'?'auto':'none';this.views.push(view);
  }
  this.observer=new IntersectionObserver(entries=>{for(const entry of entries){const v=this.views.find(v=>v.wrap===entry.target);if(!v)continue;v.near=entry.isIntersecting;if(v.near)this.ensure(v);else v.queue.then(()=>{if(v.near||v.drag)return;v.canvas.width=0;v.canvas.height=0;$(v.side+'text').replaceChildren();v.svg.replaceChildren();v.vp=null;v.loaded=false;});}}, {root:this.viewer,rootMargin:'600px 0px'});
  this.views.forEach(v=>this.observer.observe(v.wrap));await this.num(pg);this.labels();
 });return this.queue;
 }
 overlay(){this.views.forEach(v=>v.overlay());}
}
const Lpane=new Pane('L'),Rpane=new Pane('R');function pane(s){return s==='L'?Lpane:Rpane;}
function redraw(){Lpane.overlay();Rpane.overlay();}
function setTool(t){tool=t;document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===t));for(const p of [Lpane,Rpane])for(const v of p.views){$(v.side+'text').style.pointerEvents=t==='read'?'auto':'none';v.wrap.style.touchAction=t==='read'?'auto':'none';}redraw();}
function tab(id){document.querySelectorAll('.tab-panel').forEach(x=>x.classList.toggle('active',x.id==='tab-'+id));document.querySelectorAll('.tab-bar button').forEach((x,i)=>x.classList.toggle('active',['notes','marks','meta'][i]===id));}
function selectMark(id){selected=id;const m=marks.find(x=>x.id===id);if(m)Rpane.num(m.page);redraw();tab('marks');}
function eraseActive(){if(!selected)return;history();marks=marks.filter(m=>m.id!==selected);selected=null;changed();}
function renderRecords(){
 queueMicrotask(renderFigurePreviews);
 $('undoBtn').disabled=!undoStack.length;$('redoBtn').disabled=!redoStack.length;$('notePg').textContent=pane(activeSide).page;
 $('noteList').innerHTML=notes.length?notes.slice().sort((a,b)=>a.page-b.page).map(n=>`<div class="note-card"><button class="toolbar-btn" data-jump="${n.page}">Page ${n.page}</button><div class="txt">${esc(n.text)}</div><button class="toolbar-btn" data-edit="${esc(n.id)}">Edit</button><button class="toolbar-btn" data-delete="${esc(n.id)}">Delete</button></div>`).join(''):'<div class="empty">Add observations, questions, or review concerns.</div>';
 $('markList').innerHTML=marks.length?marks.map(m=>`<div class="mark-card"><div style="flex:1"><button class="toolbar-btn" data-mark="${esc(m.id)}">${m.note.startsWith('Figure caption:')?'Figure':esc(m.type)} · page ${m.page}</button>${m.note.startsWith('Figure caption:')?`<canvas class="figure-preview" data-figure="${esc(m.id)}" aria-label="Captured figure"></canvas>`:''}<textarea class="ni" data-id="${esc(m.id)}" aria-label="Annotation note or figure caption">${esc(m.note)}</textarea></div><button class="toolbar-btn" data-remove="${esc(m.id)}" aria-label="Delete annotation">×</button></div>`).join(''):'<div class="empty">Drag over a figure to capture it and add a caption, or annotate either page.</div>';
}
async function renderFigurePreviews(){
 const doc=pdfDoc;if(!doc)return;
 for(const canvas of document.querySelectorAll('[data-figure]')){
  const m=marks.find(m=>m.id===canvas.dataset.figure),r=m?.rects[0];if(!r)continue;
  try{const page=await doc.getPage(m.page),vp=page.getViewport({scale:1}),source=document.createElement('canvas');source.width=vp.width;source.height=vp.height;await page.render({canvasContext:source.getContext('2d'),viewport:vp}).promise;
   if(!canvas.isConnected||doc!==pdfDoc)continue;canvas.width=Math.max(1,Math.round(r.width*vp.width));canvas.height=Math.max(1,Math.round(r.height*vp.height));canvas.getContext('2d').drawImage(source,r.x*vp.width,(1-r.y-r.height)*vp.height,r.width*vp.width,r.height*vp.height,0,0,canvas.width,canvas.height);
  }catch(_){canvas.setAttribute('aria-label','Preview unavailable; open the marked page');}
 }
}
function newNote(id=null){if(!currentPid){toast('Open a paper first');return;}editId=id;const n=notes.find(n=>n.id===id);$('noteEditor').value=n?n.text:'';$('notePage').value=n?n.page:pane(activeSide).page;$('notePage').max=pdfDoc?.numPages||1;$('noteForm').hidden=false;$('noteEditor').focus();}
function saveNote(){const text=$('noteEditor').value.trim(),page=Number($('notePage').value);if(!text||!Number.isInteger(page)||page<1||page>(pdfDoc?.numPages||1)){toast('Enter a note and a valid page');return;}history();if(editId)notes.find(n=>n.id===editId).text=text;else notes.push({id:uid(),page,text:$('noteKind').value+': '+text});if(editId)notes.find(n=>n.id===editId).page=page;$('noteForm').hidden=true;editId=null;changed();}
$('noteList').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.jump)Lpane.num(b.dataset.jump);if(b.dataset.edit)newNote(b.dataset.edit);if(b.dataset.delete){history();notes=notes.filter(n=>n.id!==b.dataset.delete);changed();}});
$('markList').addEventListener('change',e=>{if(!e.target.dataset.id)return;history();marks.find(m=>m.id===e.target.dataset.id).note=e.target.value;changed();});
$('markList').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.mark)selectMark(b.dataset.mark);if(b.dataset.remove){selected=b.dataset.remove;eraseActive();}});
async function openPaper(pid){pid=pid.trim();if(!pid)return;try{await saveAll();await Lpane.queue;await Rpane.queue;const data=await(await request(API(pid))).json();const doc=await pdfjsLib.getDocument('/api/rag/pdf?id='+encodeURIComponent(pid)).promise;
 const old=pdfDoc;pdfDoc=doc;currentPid=pid;marks=data.marks;notes=data.notes;undoStack=[];redoStack=[];selected=null;dirty=false;$('noteForm').hidden=true;editId=null;$('paperInput').value=pid;
 Lpane.page=Rpane.page=1;for(const p of[Lpane,Rpane])p.scale=Math.max(.35,(p.viewer.clientWidth-24)/((await doc.getPage(1)).getViewport({scale:1}).width));await Promise.all([Lpane.render(),Rpane.render()]);await old?.destroy();renderRecords();$('statusPill').textContent='Saved · '+doc.numPages+' pages';
 try{const meta=await(await request('/api/rag/paper?id='+encodeURIComponent(pid))).json();$('metaBox').textContent=meta.title||pid;}catch(_){$('metaBox').textContent=pid;}
 }catch(e){toast('Could not open paper: '+e.message);$('statusPill').textContent='Open failed';}}
$('loadBtn').onclick=()=>openPaper($('paperInput').value);$('paperInput').onkeydown=e=>{if(e.key==='Enter')openPaper(e.target.value);};
$('noteAdd').onclick=()=>newNote();$('noteSave').onclick=saveNote;$('noteCancel').onclick=()=>{$('noteForm').hidden=true;editId=null;};$('noteEditor').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')saveNote();};
$('undoBtn').onclick=undo;$('redoBtn').onclick=redo;$('saveBtn').onclick=()=>saveAll().catch(()=>{});$('matchBtn').onclick=()=>Rpane.num(Lpane.page);
$('browseBtn').onclick=async()=>{try{const list=await(await request('/api/rag/review/papers')).json();const pid=prompt('Reviewed papers:\n'+list.map(x=>x.paper_id).join('\n')+'\nEnter paper ID:');if(pid)openPaper(pid);}catch(e){toast(e.message);}};
$('exportBtn').onclick=async()=>{try{await saveAll();if(!currentPid)return;const r=await request(API(currentPid)+'/export'),url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download='review-'+currentPid.replace(/[^\w.-]/g,'_')+'.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast(e.message);}};
document.querySelectorAll('[data-color]').forEach(b=>b.onclick=()=>{color=b.dataset.color;document.querySelectorAll('[data-color]').forEach(x=>x.classList.toggle('active',x===b));});
document.addEventListener('keydown',e=>{if(e.target.closest('input,textarea,select'))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();}});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
if(typeof pdfjsLib!=='undefined'){pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';setTool('read');const seed=$('paperIdSeed')?.value;if(seed)openPaper(seed);}else{$('statusPill').textContent='PDF viewer unavailable — reload to retry';}
