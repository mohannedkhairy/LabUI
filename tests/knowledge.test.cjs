const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const context={URLSearchParams};vm.createContext(context);
const source=fs.readFileSync(path.join(__dirname,'../submission_strategy/jfr/web/static/knowledge.js'),'utf8');
vm.runInContext(source,context);
const kg=context.LabKnowledge;

test('layout is deterministic, keeps every paper distinct and never mutates API data',()=>{
  const topics=Array.from({length:10},(_,i)=>({id:'topic:'+i,type:'Topic',name:'Topic '+i,weight:20}));
  const papers=Array.from({length:36},(_,i)=>({id:'paper:'+i,type:'Paper',name:'@author'+i}));
  const edges=papers.map((p,i)=>({source:'topic:'+(i%10),target:p.id,weight:8}));
  const nodes=[...topics,...papers],before=JSON.stringify({nodes,edges});
  const positions=kg.layoutGraph(nodes,edges);
  assert.equal(JSON.stringify({nodes,edges}),before);
  assert.equal(JSON.stringify(positions),JSON.stringify(kg.layoutGraph(nodes,edges)));
  assert.equal(new Set(positions.map(n=>`${n.x},${n.y}`)).size,nodes.length);
  assert.ok(positions.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)&&n.x>0&&n.x<1000&&n.y>0&&n.y<840));
});

test('stale map and inspector responses cannot replace a newer selection',()=>{
  const gate=kg.requestGate();const earlier=gate.next(),latest=gate.next();
  assert.equal(gate.current(earlier),false);assert.equal(gate.current(latest),true);
  gate.next();assert.equal(gate.current(latest),false);
});

test('paper and quote text is escaped and source page links encode IDs',()=>{
  assert.equal(kg.escape('<img onerror="alert(1)">'), '&lt;img onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(kg.paperURL('paper/a?x=1',3),'/research/paper/paper%2Fa%3Fx%3D1/view#page=3');
  assert.ok(!source.includes('onclick="'));
});

test('evidence-agent links carry graph scope without truncating a large topic to 80 IDs',()=>{
  const params=new URLSearchParams({q:'CO₂',year_from:'2020',year_to:'2025',category:'Characterization'});
  const url=new URL(kg.chatURL('Compare findings',Array.from({length:500},(_,i)=>'p'+i),{id:'topic:carbon-dioxide',params}),'http://local');
  assert.equal(url.searchParams.get('agent'),'evidence');
  assert.equal(url.searchParams.get('graph_node'),'topic:carbon-dioxide');
  assert.equal(url.searchParams.get('graph_q'),'CO₂');
  assert.equal(url.searchParams.get('graph_year_to'),'2025');
  assert.equal(url.searchParams.has('paper_id'),false);
  assert.ok(url.href.length<300);
});

test('chat blocks failed scope resolution and sends the resolved library scope',()=>{
  const chat=fs.readFileSync(path.join(__dirname,'../submission_strategy/jfr/web/templates/research_chat.html'),'utf8');
  const start=chat.indexOf('async function loadGraphScope(params) {'),end=chat.indexOf('function setChatPanel',start);
  const labels={};const scopeContext={URLSearchParams,Set,Error,document:{getElementById:id=>labels[id]||(labels[id]={})},fetch:async()=>({ok:true,json:async()=>({paper_ids:Array.from({length:150},(_,i)=>'paper'+i)})})};
  vm.createContext(scopeContext);
  vm.runInContext('var graphPaperScope=null,graphScopeFailed=false;'+chat.slice(start,end),scopeContext);
  return scopeContext.loadGraphScope(new URLSearchParams({graph_node:'topic:nacl'})).then(async()=>{
    assert.equal(scopeContext.graphPaperScope.length,150);
    assert.equal(scopeContext.graphScopeFailed,false);
    scopeContext.fetch=async()=>({ok:false});
    await scopeContext.loadGraphScope(new URLSearchParams({graph_node:'paper:removed'}));
    assert.equal(scopeContext.graphScopeFailed,true);
    assert.match(labels['graph-scope-label'].textContent,/no longer available/);
    assert.match(chat,/selected_paper_ids: graphPaperScope/);
    assert.match(chat,/library_only: !!graphPaperScope/);
  });
});
