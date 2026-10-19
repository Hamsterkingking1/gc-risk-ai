const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {createDemo}=require('./dist/demo-engine.js');
const cases=JSON.parse(fs.readFileSync(__dirname+'/dist/cases.json','utf8'));
function setup(){const m=new Map(),storage={getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v)};return {demo:createDemo(cases,storage),storage};}
function input(d,case_id='risk'){return {...d.read().records[case_id+':cash'],case_id,signal_id:'cash',performer:'A',reason:'가상 사유',evidence:'가상 E1',result:'가상 결과',conclusion:'가상 결론'};}
test('three scenario outcomes are preserved',()=>{assert.deepEqual(cases.slice(0,3).map(c=>c.signals.map(s=>s.flag)),[[true,true,true,true,true],[false,false,false,false,false],[null,null,null,null,null]]);});
test('fresh records do not fabricate results',()=>{const {demo}=setup();assert.match(demo.exportText('risk'),/실제 수행 결과: 미입력/);});
test('records survive a new engine instance',()=>{const {demo,storage}=setup();demo.save(input(demo));assert.equal(createDemo(cases,storage).read().records['risk:cash'].result,'가상 결과');});
test('history retains the saved actor and payload',()=>{const {demo}=setup();demo.save(input(demo));assert.equal(demo.read().history[0].actor,'A');assert.equal(JSON.parse(demo.read().history[0].payload).evidence,'가상 E1');});
test('review request requires evidence',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 요청',evidence:''}),/증거/);});
test('review completion requires a prior request',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'B',review_note:'확인'}),/먼저 검토 요청/);});
test('review request can be completed by a different reviewer',()=>{const {demo}=setup();const p=input(demo);p.status='검토 요청';Object.assign(p,demo.save(p));Object.assign(p,{status:'검토 완료',reviewer:'B',review_note:'확인'});assert.equal(demo.save(p).status,'검토 완료');assert.match(demo.exportText('risk'),/검토자: B/);});
test('same reviewer cannot complete',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'A',review_note:'확인'}),/다른 검토자/);});
test('unresolved items block completion',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo),status:'검토 완료',reviewer:'B',review_note:'확인',unresolved:'추가 자료'}),/미해결/);});
test('missing source blocks completion',()=>{const {demo}=setup();assert.throws(()=>demo.save({...input(demo,'missing'),status:'검토 완료',reviewer:'B',review_note:'확인'}),/기초 자료/);});
test('stale window cannot overwrite a newer record',()=>{const {demo}=setup(),p=input(demo);demo.save(p);assert.throws(()=>demo.save(p),/다른 창/);});
test('edited review content must be resubmitted',()=>{const {demo}=setup(),p=input(demo);p.status='검토 요청';Object.assign(p,demo.save(p));Object.assign(p,{status:'검토 완료',reviewer:'B',review_note:'확인',result:'바뀐 결과'});assert.throws(()=>demo.save(p),/내용이 바뀌었습니다/);});
test('storage failure is reported without claiming save success',()=>{const d=createDemo(cases,{getItem:()=>null,setItem:()=>{throw Error('quota')}});assert.throws(()=>d.save(input(d)),/저장할 수 없습니다/);});
