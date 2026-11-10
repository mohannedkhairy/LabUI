/* Local SVG research explorer. No CDN, GPU, simulation loop or third-party JS. */
(function (global) {
  'use strict';
  const API = '/api/rag/knowledge';
  const NS = 'http://www.w3.org/2000/svg';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const paperURL = (id, page) => '/research/paper/' + encodeURIComponent(id) + '/view' + (page ? '#page=' + encodeURIComponent(page) : '');

  function requestGate() {
    let version = 0;
    return {next: () => ++version, current: value => value === version};
  }

  function layoutGraph(nodes, edges) {
    const topics = nodes.filter(n => n.type === 'Topic');
    const papers = nodes.filter(n => n.type === 'Paper');
    const positions = new Map();
    topics.forEach((node, i) => {
      const angle = -Math.PI / 2 + i * 2 * Math.PI / Math.max(topics.length, 1);
      positions.set(node.id, {x: 500 + 230 * Math.cos(angle), y: 420 + 200 * Math.sin(angle), angle});
    });
    const groups = new Map(topics.map(n => [n.id, []]));
    papers.forEach(node => {
      const links = edges.filter(e => e.target === node.id).sort((a,b) => b.weight-a.weight || a.source.localeCompare(b.source));
      const main = links.find(e => groups.has(e.source));
      if (main) groups.get(main.source).push(node);
    });
    // Each topic owns one arc; paper nodes remain distinct even in dense hubs.
    topics.forEach((topic, i) => {
      const group = groups.get(topic.id);
      const arc = 2 * Math.PI / Math.max(topics.length, 1);
      group.forEach((node, j) => {
        const angle = -Math.PI/2 + i*arc + ((j+1)/(group.length+1)-0.5)*arc*0.85;
        const ring = 335 + (j % 2) * 48;
        positions.set(node.id, {x:500+ring*Math.cos(angle),y:420+ring*Math.sin(angle)});
      });
    });
    return nodes.map(node => ({...node,...(positions.get(node.id) || {x:500,y:420})}));
  }

  function chatURL(query, paperIds, scope) {
    const params = new URLSearchParams({q:query,agent:'evidence'});
    if(scope) {
      params.set('graph_node',scope.id);
      for(const [key,value] of scope.params) if(['q','year_from','year_to'].includes(key))params.set('graph_'+key,value);
    } else paperIds.slice(0,80).forEach(id => params.append('paper_id',id));
    return '/research/chat?' + params;
  }

  // Small pure helpers are exposed for behavior tests without a browser.
  global.LabKnowledge = {escape:esc,layoutGraph,requestGate,paperURL,chatURL};
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const mapGate = requestGate(), detailGate = requestGate();
  let data = {nodes:[],edges:[]}, selected = '', focus = '', view = 'map';
  let svg, group, transform = {x:0,y:0,k:1}, drag = null, moved = false;
  let previousRunning = false, pollTimer = null;

  async function api(path, options) {
    const response = await fetch(API + path, options);
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('The server returned an unreadable response.'); }
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request failed ('+response.status+').');
    return result;
  }

  function message(text, error = false) {
    $('kg-status').textContent = text;
    $('kg-status').classList.toggle('error', error);
  }

  function scopeParams() {
    const params = new URLSearchParams();
    for (const [id,key] of [['kg-q','q'],['kg-category','category'],['kg-from','year_from'],['kg-to','year_to'],['kg-min','min_papers']]) {
      if ($(id).value.trim()) params.set(key,$(id).value.trim());
    }
    return params;
  }

  function shareURL() {
    const params = scopeParams();
    if (focus) params.set('focus',focus);
    if (selected) params.set('node',selected);
    if (view !== 'map') params.set('view',view);
    history.replaceState(null,'',location.pathname + (params.size ? '?'+params : ''));
  }

  async function loadMap() {
    const ticket = mapGate.next();
    detailGate.next();
    const params = scopeParams();
    if (focus) params.set('focus',focus);
    message('Finding research connections…');
    try {
      const result = await api('?'+params);
      if (!mapGate.current(ticket)) return;
      data = result;
      renderStats(result.stats);
      renderTopics(); drawMap(); renderInsights();
      $('kg-render-count').textContent = result.shown_papers + ' of ' + result.scope_papers + ' papers';
      $('kg-map-empty').hidden = result.nodes.length > 0;
      message(result.stats.papers ? `${result.scope_papers} papers in this view · showing representative papers and up to 14 topics. Select a topic or paper to inspect its sources.` : 'Your library has not been mapped yet. Select Refresh map to connect your papers.');
      const exports = scopeParams(); exports.delete('category'); exports.delete('min_papers');
      $('kg-json').href = API+'/export?'+exports;
      exports.set('format','csv'); $('kg-csv').href = API+'/export?'+exports;
      shareURL();
      if (selected) await inspect(selected, false);
    } catch (error) {
      if (mapGate.current(ticket)) message(error.message,true);
    }
  }

  function renderStats(stats) {
    for (const [id,key] of [['kg-papers','mapped_papers'],['kg-topics','topics'],['kg-passages','passages'],['kg-findings','findings']]) {
      $(id).textContent = Number(stats[key] || 0).toLocaleString();
    }
    $('kg-papers').title = `${stats.mapped_papers || 0} mapped out of ${stats.papers || 0} indexed papers`;
    $('kg-findings').title = `${stats.papers_with_findings || 0} papers with findings; ${stats.checked_chunks || 0} passages checked. Quotes are source-checked; interpretations still need review.`;
  }

  function renderTopics() {
    const fragment = document.createDocumentFragment();
    (data.topics || []).forEach(topic => {
      const button = document.createElement('button');
      button.className = 'kg-topic-btn'; button.dataset.node = topic.id;
      button.title = topic.category + ' · ' + topic.aliases.join(', ');
      const dot = document.createElement('i');
      const node = data.nodes.find(n => n.id === topic.id);
      dot.style.background = node?.color || '#8894a8';
      const name = document.createElement('strong'); name.textContent = topic.name;
      const count = document.createElement('span'); count.textContent = topic.paper_count;
      button.append(dot,name,count); fragment.append(button);
    });
    $('kg-topic-list').replaceChildren(fragment);
  }

  function svgElement(tag, attrs = {}, text) {
    const node = document.createElementNS(NS,tag);
    for (const [key,value] of Object.entries(attrs)) node.setAttribute(key,value);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function drawMap() {
    const nodes = layoutGraph(data.nodes,data.edges), byId = new Map(nodes.map(node => [node.id,node]));
    svg = svgElement('svg',{viewBox:'0 0 1000 840',role:'group','aria-label':'Paper and topic map. Nodes are keyboard accessible; source evidence is also available in the topic list.'});
    group = svgElement('g'); svg.append(group);
    for (const edge of data.edges) {
      const source = byId.get(edge.source), target = byId.get(edge.target);
      if (!source || !target) continue;
      const line = svgElement('line',{x1:source.x,y1:source.y,x2:target.x,y2:target.y,class:'kg-link','data-source':edge.source,'data-target':edge.target});
      line.append(svgElement('title',{},'Explicit topic mention. Select either endpoint to read its source passages.'));
      group.append(line);
    }
    for (const node of nodes) {
      const g = svgElement('g',{transform:`translate(${node.x},${node.y})`,class:'kg-node',tabindex:0,role:'button','aria-label':(node.title || node.name)+(node.type==='Topic'?`, ${node.paper_count} papers`:''),'data-node':node.id});
      g.append(svgElement('circle',{r:node.type==='Topic'?13+Math.min(8,Math.sqrt(node.weight)):6,fill:node.color}));
      g.append(svgElement('title',{},node.title || `${node.name} · ${node.paper_count} papers`));
      const label = svgElement('text',{'text-anchor':'middle',class:node.type==='Paper'?'kg-paper-label':''});
      if(node.type==='Topic') {
        const lines=[''];
        for(const word of node.name.split(/\s+/)) {
          if(lines[lines.length-1].length+word.length>18 && lines[lines.length-1])lines.push(word);
          else lines[lines.length-1]+=(lines[lines.length-1]?' ':'')+word;
        }
        label.setAttribute('y',-25-(lines.length-1)*19);
        lines.forEach((line,i)=>label.append(svgElement('tspan',{x:0,dy:i?19:0},line)));
      } else {label.setAttribute('y',25);label.textContent=node.name;}
      g.append(label);
      g.addEventListener('click',event => { event.stopPropagation(); if (!moved) inspect(node.id); });
      g.addEventListener('keydown',event => { if (['Enter',' '].includes(event.key)) {event.preventDefault();inspect(node.id);} });
      group.append(g);
    }
    svg.addEventListener('wheel',event => {event.preventDefault();zoomBy(event.deltaY<0?1.12:1/1.12);},{passive:false});
    svg.addEventListener('pointerdown',event => {
      if (event.button !== 0) return;
      drag = {x:event.clientX,y:event.clientY,tx:transform.x,ty:transform.y}; moved = false;
      // Keep clicks on nodes intact; capture only background drags.
      if (!event.target.closest('[data-node]')) svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener('pointermove',event => {
      if (!drag) return;
      const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
      if (Math.abs(dx)+Math.abs(dy)>5) moved=true;
      const rect = svg.getBoundingClientRect();
      const ratio = Math.max(1000/Math.max(rect.width,1),840/Math.max(rect.height,1));
      transform.x=drag.tx+dx*ratio; transform.y=drag.ty+dy*ratio; applyTransform();
    });
    for (const name of ['pointerup','pointercancel','pointerleave']) svg.addEventListener(name,() => {drag=null;});
    svg.addEventListener('click',event => {if (!moved && !event.target.closest('[data-node]')) clearSelection();});
    $('kg-canvas').replaceChildren(svg);
    transform={x:0,y:0,k:1}; applyTransform(); highlight();
  }

  function applyTransform() {if (group) group.setAttribute('transform',`translate(${transform.x},${transform.y}) scale(${transform.k})`);}
  function zoomBy(factor) {
    const next=Math.min(4,Math.max(.5,transform.k*factor)),ratio=next/transform.k;
    transform.x=500-(500-transform.x)*ratio;transform.y=420-(420-transform.y)*ratio;transform.k=next;applyTransform();
  }
  function highlight() {
    const near = new Set([selected]);
    data.edges.forEach(edge => {if(edge.source===selected || edge.target===selected){near.add(edge.source);near.add(edge.target);}});
    $('kg-canvas').querySelectorAll('[data-node]').forEach(el => {el.classList.toggle('selected',el.dataset.node===selected);el.classList.toggle('dim',!!selected && !near.has(el.dataset.node));});
    $('kg-topic-list').querySelectorAll('[data-node]').forEach(el => el.classList.toggle('selected',el.dataset.node===selected));
    $('kg-canvas').querySelectorAll('.kg-link').forEach(el => el.classList.toggle('active',!!selected&&(el.dataset.source===selected||el.dataset.target===selected)));
  }

  function sourceHTML(row, isClaim = false) {
    return `<article class="kg-source"><span class="kg-citation">@${esc(row.citation_key || '')}</span> <span class="kg-muted">${esc(row.section_name || 'Source')}${row.page_start?' · p. '+esc(row.page_start):''}</span>${isClaim?`<p><strong>${esc(row.source)} ${esc(row.relation.replaceAll('_',' '))} ${esc(row.target)}</strong></p>`:''}<blockquote>${esc(row.quote)}</blockquote>${isClaim?`<p class="kg-muted">Conditions: ${esc(row.conditions || 'Not stated in this quote')}<br>Model interpreted · source quote verified</p>`:''}<a href="${paperURL(row.paper_id,row.page_start)}" target="_blank" rel="noopener">${esc(row.title || 'Read source')} ↗</a></article>`;
  }

  async function inspect(nodeId, setSelection = true) {
    if(setSelection && !data.nodes.some(node=>node.id===nodeId) && focus!==nodeId) {
      selected=nodeId;focus=nodeId;
      if(nodeId.startsWith('paper:'))$('kg-min').value='1';
      await loadMap();return;
    }
    const ticket = detailGate.next();
    if (setSelection) {selected=nodeId;highlight();shareURL();}
    $('kg-close').hidden=false; $('kg-inspector-title').textContent='Loading sources…';
    $('kg-inspector-body').textContent='';
    const params=scopeParams();params.delete('category');params.delete('min_papers');params.set('id',nodeId);
    try {
      const detail=await api('/node?'+params);
      if (!detailGate.current(ticket)) return;
      const node=detail.node;
      $('kg-inspector-title').textContent=node.title || node.name;
      const query=node.type==='Paper'?`Compare the methods, findings and limitations of ${node.title} with related papers. Cite the supplied sources and preserve experimental conditions.`:`What do the selected papers report about ${node.name}? Compare findings, methods and conditions, citing sources.`;
      const actions=`<div class="kg-inspector-actions"><button class="toolbar-btn" data-focus="${esc(nodeId)}">Focus this neighborhood</button><a class="toolbar-btn" href="${esc(chatURL(query,detail.paper_ids,{id:nodeId,params}))}">Ask evidence agent →</a>${node.type==='Paper'?`<a class="toolbar-btn" href="${paperURL(node.paper_id)}" target="_blank" rel="noopener">Read paper ↗</a>`:''}</div>`;
      const topics=detail.topics.slice(0,16).map(topic=>`<button class="kg-chip" data-node="${esc(topic.id)}">${esc(topic.name)}</button>`).join('');
      $('kg-inspector-body').innerHTML=`<p class="kg-muted">${esc(node.category)} · ${node.paper_count} ${node.paper_count===1?'paper':'papers'}${node.year?' · '+esc(node.year):''}</p>${node.authors?`<p>${esc(node.authors)}</p>`:''}${node.abstract?`<details><summary>Abstract</summary><p>${esc(node.abstract)}</p></details>`:''}${actions}<h3>Connected topics</h3><div>${topics}</div>${node.type==='Topic'?`<details class="kg-all-papers"><summary>Browse all ${node.paper_count} connected papers</summary><div id="kg-paper-page">${paperListHTML(detail.papers)}</div><button id="kg-more-papers" class="toolbar-btn" ${detail.next_paper_offset===null?'hidden':''}>More papers</button></details>`:''}<h3>Source-checked findings (${detail.claims.length})</h3>${detail.claims.length?detail.claims.map(claim=>sourceHTML(claim,true)).join(''):'<p class="kg-muted">No findings extracted here yet. Use Evidence tools → Extract findings to inspect a batch with your local model.</p>'}<h3>Why these papers connect</h3><p class="kg-muted">These excerpts contain explicit topic mentions; a mention alone does not establish a finding.</p>${detail.passages.map(row=>sourceHTML(row)).join('') || '<p>No source passages in this scope.</p>'}${detail.related.length?'<h3>Related reading</h3>'+detail.related.map(p=>`<div class="kg-related"><button data-node="${esc(p.id)}">${esc(p.title)}</button><div class="kg-citation">${esc(p.name)}</div><p class="kg-muted">Shared: ${esc(p.shared_topics.join(', '))}</p></div>`).join(''):''}`;
      const more=$('kg-more-papers');
      if(more)more.addEventListener('click',async()=>{
        more.disabled=true;
        params.set('paper_offset',String(detail.next_paper_offset));
        try {
          const page=await api('/node?'+params);
          if(!detailGate.current(ticket))return;
          $('kg-paper-page').insertAdjacentHTML('beforeend',paperListHTML(page.papers));
          detail.next_paper_offset=page.next_paper_offset;
          more.hidden=page.next_paper_offset===null;
        }catch(error){message(error.message,true);}finally{more.disabled=false;}
      });
      $('kg-inspector').scrollTop=0;
    } catch(error) {if(detailGate.current(ticket)){ $('kg-inspector-title').textContent='Sources unavailable';$('kg-inspector-body').textContent=error.message;}}
  }

  function paperListHTML(papers) {
    return (papers || []).map(p=>`<div class="kg-related"><button data-node="${esc(p.id)}">${esc(p.title)}</button><div class="kg-citation">${esc(p.name)} · ${esc(p.year || 'Year unknown')}</div></div>`).join('');
  }

  function clearSelection() {
    selected='';detailGate.next();highlight();shareURL();$('kg-close').hidden=true;
    $('kg-inspector-title').textContent='Explore a connection';
    $('kg-inspector-body').textContent='Select a topic or a paper to see source passages, extracted findings and related reading.';
  }

  function renderInsights() {
    $('kg-bridges').innerHTML=(data.bridges || []).map(p=>`<article class="kg-insight"><h3>${esc(p.title)}</h3><span class="kg-citation">${esc(p.name)}</span><p class="kg-muted">Connects ${p.category_count} topic categories</p><p>${p.topics.map(t=>`<span class="kg-chip">${esc(t)}</span>`).join('')}</p><button class="toolbar-btn" data-inspect="${esc(p.id)}">Explore this paper →</button></article>`).join('') || '<div class="kg-insight">No papers span three topic categories in this view. Widen the search to find more reading connections.</div>';
    $('kg-gaps').innerHTML=(data.gaps || []).map(pair=>`<article class="kg-insight"><h3>${esc(pair.name)}</h3><p class="kg-muted">${pair.left_count} and ${pair.right_count} papers respectively · no joint mentions</p><button class="toolbar-btn" data-inspect="${esc(pair.left)}">Explore first topic</button> <button class="toolbar-btn" data-inspect="${esc(pair.right)}">Explore second topic</button></article>`).join('') || '<div class="kg-insight">No separate, well-represented topic pairs in this view. This is a library coverage check, not a novelty assessment.</div>';
    $('kg-comparisons').innerHTML=(data.comparisons || []).map(pair=>`<article class="kg-insight"><h3>${esc(pair.source)} → ${esc(pair.target)}</h3><p class="kg-muted">${esc(pair.label)}</p>${pair.claims.map(c=>sourceHTML(c,true)).join('')}</article>`).join('') || `<div class="kg-insight"><h3>${data.stats.findings?'No differing effects in this view':'Build the evidence layer'}</h3><p>Extract findings from selected papers or topics using Evidence tools. Only claims carrying a verified source quote are stored. Comparisons appear when different papers report different effects for the same pair of properties.</p><p class="kg-muted">${data.stats.findings || 0} findings across ${data.stats.papers_with_findings || 0} papers. Absence of a comparison does not show scientific agreement.</p></div>`;
  }

  function showView(name) {
    if (!['map','findings','reading'].includes(name)) name='map';
    view=name;
    document.querySelectorAll('[data-view]').forEach(button=>{const active=button.dataset.view===name;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;});
    for (const key of ['map','findings','reading']) $('kg-'+key+'-panel').hidden=key!==name;
    shareURL();
  }

  async function startJob(kind) {
    try {
      const options={method:'POST',headers:{'Content-Type':'application/json'}};
      if(kind==='extract') {
        const params=scopeParams(),node=selected || focus;
        const body={max_chunks:12};
        // The actual list comes from the current year/query scope, so an
        // extraction never silently reaches papers hidden by active filters.
        if (node || params.get('q') || params.get('year_from') || params.get('year_to')) {
          const id=node || data.topics?.[0]?.id;
          if (!id) throw new Error('Choose a topic or paper in this view first.');
          const scope=new URLSearchParams(params);scope.delete('category');scope.delete('min_papers');scope.set('id',id);
          const detail=await api('/node?'+scope);
          body.paper_ids=detail.paper_ids;
          if(id.startsWith('topic:')) body.topic_id=id.slice(6);
        }
        options.body=JSON.stringify(body);
      }
      await api('/'+(kind==='extract'?'extract':'build'),options);
      previousRunning=true;
      document.querySelector('.kg-actions').open=false;
      await pollStatus();
    } catch(error){message(error.message,true);}
  }

  async function pollStatus() {
    clearTimeout(pollTimer);
    try {
      const state=await api('/status');renderStats(state);
      const select=$('kg-category');
      if(select.options.length===1) for(const category of state.categories){const option=document.createElement('option');option.value=category;option.textContent=category;select.append(option);}
      const pendingCategory=new URLSearchParams(location.search).get('category');
      if(pendingCategory && !select.value && Array.from(select.options).some(o=>o.value===pendingCategory))select.value=pendingCategory;
      const job=state.job;
      $('kg-refresh').disabled=job.running; $('kg-extract').disabled=job.running;
      $('kg-job').hidden=!job.running && !job.message;
      $('kg-job-message').textContent=(job.error?job.error+' · ':'')+job.message;
      $('kg-stop').hidden=!job.running || job.kind!=='findings';
      $('kg-progress').hidden=!job.running;
      $('kg-progress').max=Math.max(job.total,1);$('kg-progress').value=job.done;
      if (previousRunning && !job.running) {await loadMap();}
      if(!job.running && job.error)message(job.error,true);
      if(state.needs_refresh && !job.running)message('The library has changed. Refresh map to include the latest papers.');
      previousRunning=job.running;
      pollTimer=setTimeout(pollStatus,job.running?2000:15000);
    } catch(error){message(error.message,true);pollTimer=setTimeout(pollStatus,15000);}
  }

  document.addEventListener('DOMContentLoaded',async()=>{
    const params=new URLSearchParams(location.search);
    for(const [id,key] of [['kg-q','q'],['kg-from','year_from'],['kg-to','year_to'],['kg-min','min_papers']])if(params.has(key))$(id).value=params.get(key);
    focus=params.get('focus') || ''; selected=params.get('node') || '';
    $('kg-filters').addEventListener('submit',event=>{event.preventDefault();focus='';clearSelection();loadMap();});
    $('kg-clear').addEventListener('click',()=>{$('kg-filters').reset();focus='';clearSelection();loadMap();});
    $('kg-refresh').addEventListener('click',()=>startJob('index'));
    $('kg-extract').addEventListener('click',()=>startJob('extract'));
    $('kg-stop').addEventListener('click',async()=>{try{await api('/cancel',{method:'POST'});await pollStatus();}catch(error){message(error.message,true);}});
    $('kg-close').addEventListener('click',clearSelection);
    $('kg-zoom-in').addEventListener('click',()=>zoomBy(1.3));$('kg-zoom-out').addEventListener('click',()=>zoomBy(1/1.3));
    $('kg-fit').addEventListener('click',()=>{transform={x:0,y:0,k:1};applyTransform();});
    $('kg-root').addEventListener('click',event=>{
      const button=event.target.closest('[data-node],[data-query],[data-focus],[data-inspect],[data-view]');
      if(!button || button.namespaceURI===NS)return;
      if(button.dataset.view){showView(button.dataset.view);return;}
      if(button.dataset.query){$('kg-q').value=button.dataset.query;focus='';clearSelection();loadMap();return;}
      if(button.dataset.focus){focus=button.dataset.focus;loadMap();return;}
      if(button.dataset.inspect){showView('map');inspect(button.dataset.inspect);return;}
      if(button.dataset.node)inspect(button.dataset.node);
    });
    document.querySelector('.kg-tabs').addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();const tabs=Array.from(document.querySelectorAll('[data-view]'));
      let index=tabs.findIndex(tab=>tab.dataset.view===view);
      index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      showView(tabs[index].dataset.view);tabs[index].focus();
    });
    await pollStatus(); showView(params.get('view') || 'map'); await loadMap();
    document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(pollTimer);else pollStatus();});
  });
})(typeof globalThis!=='undefined'?globalThis:this);
