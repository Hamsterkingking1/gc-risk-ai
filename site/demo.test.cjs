const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {createDemo}=require('./dist/demo-engine.js');
const cases=JSON.parse(fs.readFileSync(__dirname+'/dist/cases.json','utf8'));
test('source-linked debt excludes leases and current bonds are not added twice',()=>{const q=require('./dist/quality.js');const c=cases.find(c=>c.name==='삼성전자');assert.deepEqual(q.debtValues(c,2025),[15382751000000n,38189885000000n]);const broken=structuredClone(c);broken.debt_reconciliation['2025'].parts.push(broken.debt_reconciliation['2025'].parts[0]);assert.equal(q.debtValues(broken,2025),null);assert.equal(q.enrich(broken,[{},{},{},{},{}])[3].flag,null);});
test('all three years and original audit flags are retained',()=>{const d=cases.find(c=>c.name==='대구백화점'),s=cases.find(c=>c.name==='STX');assert.equal(d.annual_financials['2023'].assets,'26217320178');assert.equal(d.audit_by_year['2024'].flag,true);assert.equal(s.audit_by_year['2025'].opinion,'의견거절');assert.equal(s.audit_by_year['2025'].flag,true);});
function setup(){const m=new Map(),storage={getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v)};return {demo:createDemo(cases,storage),storage};}
function input(d,case_id='real_011230_2025_OFS'){return {...d.read().records[case_id+':cash'],case_id,signal_id:'cash',performer:'A',reason:'가상 사유',evidence:'가상 E1',result:'가상 결과',conclusion:'가상 결론'};}
test('only real DART companies are included in cases.json',()=>{assert.equal(cases.every(c=>c.real===true),true);assert.deepEqual(cases.find(c=>c.id==='real_011230_2025_OFS').signals.map(s=>s.flag),[true,true,true,true,true]);assert.deepEqual(cases.find(c=>c.id==='real_005930_2025_OFS').signals.map(s=>s.flag),[false,false,false,false,false]);});
test('fresh records do not fabricate results',()=>{const {demo}=setup();assert.match(demo.exportText('real_011230_2025_OFS'),/실제 수행 결과: 미입력/);});
test('records survive a new engine instance',()=>{const {demo,storage}=setup();demo.save(input(demo));assert.equal(createDemo(cases,storage).read().records['real_011230_2025_OFS:cash'].result,'가상 결과');});
test('history retains the saved actor and payload',()=>{const {demo}=setup();demo.save(input(demo));assert.equal(demo.read().history[0].actor,'A');assert.equal(JSON.parse(demo.read().history[0].payload).evidence,'가상 E1');});
test('review request requires evidence',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 요청',evidence:''}),/증거/);});
test('review completion requires a prior request',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'B',review_note:'확인'}),/먼저 검토 요청/);});
test('review request can be completed by a different reviewer',()=>{const {demo}=setup();const p=input(demo);p.status='검토 요청';Object.assign(p,demo.save(p));Object.assign(p,{status:'검토 완료',reviewer:'B',review_note:'확인'});assert.equal(demo.save(p).status,'검토 완료');assert.match(demo.exportText('real_011230_2025_OFS'),/검토자: B/);});
test('same reviewer cannot complete',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'A',review_note:'확인'}),/다른 검토자/);});
test('unresolved items block completion',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'B',review_note:'확인',unresolved:'추가 자료'}),/미해결/);});
test('missing source blocks completion',()=>{const {demo}=setup();const c=demo.addCustomCase({name:'결측기업',cash_2023:'',cash_2024:'',cash_2025:''});assert.throws(()=>demo.save({...input(demo,c.id),status:'검토 완료',reviewer:'B',review_note:'확인'}),/기초 자료/);});
test('stale window cannot overwrite a newer record',()=>{const {demo}=setup(),p=input(demo);demo.save(p);assert.throws(()=>demo.save(p),/다른 창/);});
test('edited review content must be resubmitted',()=>{const {demo}=setup(),p=input(demo);p.status='검토 요청';Object.assign(p,demo.save(p));Object.assign(p,{status:'검토 완료',reviewer:'B',review_note:'확인',result:'바뀐 결과'});assert.throws(()=>demo.save(p),/내용이 바뀌었습니다/);});
test('storage failure is reported without claiming save success',()=>{const d=createDemo(cases,{getItem:()=>null,setItem:()=>{throw Error('quota')}});assert.throws(()=>d.save(input(d)),/저장할 수 없습니다/);});
test('one won negative manual input is retained',()=>{
  const {demo}=setup();
  const c=demo.addCustomCase({name:'소액손실',cash_2023:'1',cash_2024:'2',cash_2025:'-0.000001'});
  assert.equal(c.cash[2],'-0.000001');
  assert.equal(c.signals[1].flag,true);
  assert.match(c.signals[1].value,/-1원/);
  assert.match(c.signals[1].value,/3년 연속 음수: 미해당/);
});
test('invalid inputs are reported instead of rounded or treated as zero',()=>{
  const {demo}=setup();
  for(const v of ['NaN','Infinity','1,2','0.0000001']){
    assert.throws(()=>demo.addCustomCase({name:'검사',assets:v}),/금액/);
  }
});
test('legacy completed record remains intact but requires a new review',()=>{
  const {demo,storage}=setup();
  const p=input(demo);
  storage.setItem('gc-audit-demo-v1',JSON.stringify({records:{[p.case_id+':cash']:{...p,status:'검토 완료'}},history:[]}));
  const r=demo.read().records[p.case_id+':cash'];
  assert.equal(r.status,'검토 요청');
  assert.equal(r.needs_rule_review,true);
  assert.equal(r.evidence,p.evidence);
  assert.equal(JSON.parse(storage.getItem('gc-audit-demo-v1')).records[p.case_id+':cash'].status,'검토 완료');
});
test('missing comparison year blocks completion without hiding current cash risk',()=>{
  const {demo}=setup();
  const c=demo.addCustomCase({name:'비교누락',cash_2023:'',cash_2024:'1',cash_2025:'-1'});
  assert.equal(c.signals[1].flag,true);
  assert.throws(()=>demo.save({...input(demo,c.id),status:'검토 완료',reviewer:'B',review_note:'확인'}),/기초 자료/);
});

