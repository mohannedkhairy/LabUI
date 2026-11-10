const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const template = fs.readFileSync(path.join(__dirname,'../submission_strategy/jfr/web/templates/base.html'),'utf8');
const search = template.slice(template.indexOf('  async function cmdkRender(q) {'),template.indexOf('  function cmdkPaint() {'))
  .replaceAll('{{ workspace.id }}','lab');

function searchContext(fetch) {
  const hint = {textContent:''};
  const context = {fetch,document:{getElementById:()=>hint},encodeURIComponent};
  vm.createContext(context);
  vm.runInContext('var cmdkSeq=0,cmdkRows=[],cmdkIdx=0;function cmdkStatic(){return [{label:"Research overview",href:"/spaces/research"}];} function cmdkPaint(){};'+search,context);
  return context;
}

test('global palette keeps cross-space navigation and shows actual task/project/paper matches', async () => {
  let requested;
  const matches=[{label:'Saline task',tag:'Task',href:'/plan?open=task:one'},
    {label:'Saline draft',tag:'Writing project',href:'/write/one'},
    {label:'Saline paper',tag:'Paper',href:'/research/paper/one/view'}];
  const context=searchContext(async url=>{requested=url;return {ok:true,json:async()=>({items:matches})};});
  await context.cmdkRender('saline');
  assert.ok(requested.startsWith('/api/workspaces/search?'));
  assert.equal(context.cmdkRows.length,4);
  assert.equal(context.cmdkRows[3].href,'/research/paper/one/view');
});

test('an earlier search response cannot replace a newer query', async () => {
  let resolveOld;
  const context=searchContext(async url=>url.includes('q=old&')?new Promise(resolve=>{resolveOld=resolve;}):{ok:true,json:async()=>({items:[{label:'New match',href:'/write/new'}]})});
  const pending=context.cmdkRender('old');
  await context.cmdkRender('new');
  resolveOld({ok:true,json:async()=>({items:[{label:'Old match',href:'/write/old'}]})});
  await pending;
  assert.equal(context.cmdkRows[1].label,'New match');
});

test('agent cards select the requested valid mode and reject unknown modes', async () => {
  const chat=fs.readFileSync(path.join(__dirname,'../submission_strategy/jfr/web/templates/research_chat.html'),'utf8');
  const start=chat.indexOf('async function loadAgents() {');
  const end=chat.indexOf('// Skill-backed agents',start);
  const source=chat.slice(start,end);
  for (const [requested,expected] of [['evidence','evidence'],['__proto__','chat']]) {
    const select={value:'chat',innerHTML:'',appendChild(option){if(option.selected)this.value=option.value;}};
    const context={location:{search:'?agent='+requested},URLSearchParams,
      document:{getElementById:()=>select,createElement:()=>({})},
      fetch:async()=>({json:async()=>({chat:{name:'Chat'},evidence:{name:'Claim Evidence'}})})};
    vm.createContext(context);
    vm.runInContext('var currentAgent="chat";async function loadSections(){};function syncSectionSelect(){};'+source,context);
    await context.loadAgents();
    assert.equal(context.currentAgent,expected);
    assert.equal(select.value,expected);
  }
});
