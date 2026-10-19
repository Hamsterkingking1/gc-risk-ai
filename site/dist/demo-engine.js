(function (root) {
  'use strict';
  const FIELDS=['performer','reviewer','requests','procedure','reason','evidence','result','conclusion','unresolved','review_note','status'];
  const STATUSES=['미착수','자료 요청','수행 중','검토 요청','검토 완료'];
  const KEY='gc-audit-demo-v1';
  function createDemo(cases, storage) {
    const clone=x=>JSON.parse(JSON.stringify(x));
    function initialRecord(s) {
      return {...Object.fromEntries(FIELDS.map(k=>[k,''])),requests:s.requests,procedure:s.procedure,status:'미착수',version:0};
    }
    function read() {
      const raw=storage.getItem(KEY);
      let saved;
      try { saved=raw?JSON.parse(raw):{records:{},history:[]}; }
      catch { throw Error('저장 기록을 읽을 수 없습니다. 브라우저 데이터를 지우기 전에 기록을 확인해주세요.'); }
      if(!saved||!saved.records||!Array.isArray(saved.history))throw Error('저장 기록 형식이 올바르지 않습니다.');
      const records={};
      for(const c of cases)for(const s of c.signals)records[c.id+':'+s.id]={...initialRecord(s),...(saved.records[c.id+':'+s.id]||{})};
      return {cases:clone(cases),records,history:saved.history};
    }
    function save(data) {
      const c=cases.find(c=>c.id===data.case_id),s=c?.signals.find(s=>s.id===data.signal_id);
      if(!s)throw Error('알 수 없는 업무 또는 신호입니다.');
      const p=Object.fromEntries(FIELDS.map(k=>[k,String(data[k]??'').trim()]));
      if(Object.values(p).some(v=>v.length>20000))throw Error('입력 항목은 20,000자 이내로 작성하세요.');
      if(!p.performer||!STATUSES.includes(p.status))throw Error('수행자 이름과 올바른 업무 상태가 필요합니다.');
      if(['검토 요청','검토 완료'].includes(p.status)&&['procedure','reason','evidence','result','conclusion'].some(k=>!p[k]))throw Error('검토 요청 전 절차·선택 이유·증거·수행 결과·결론을 입력하세요.');
      if(p.status==='검토 완료') {
        if(p.unresolved)throw Error('미해결 사항이 남아 있습니다. 보완 후 검토를 완료하세요.');
        if(s.flag===null)throw Error('기초 자료가 부족한 사례는 이 시제품에서 검토 완료할 수 없습니다.');
        if(!p.reviewer||p.reviewer===p.performer||!p.review_note)throw Error('수행자와 다른 검토자 및 검토 의견이 필요합니다.');
      }
      const db=read(),key=c.id+':'+s.id,old=db.records[key];
      if(data.version!==old.version)throw Error('다른 창에서 기록이 변경되었습니다. 새로고침 후 다시 입력하세요.');
      if(p.status==='검토 완료') {
        if(!['검토 요청','검토 완료'].includes(old.status))throw Error('먼저 검토 요청 상태로 저장한 후 검토를 완료하세요.');
        if(['requests','procedure','reason','evidence','result','conclusion','performer'].some(k=>p[k]!==old[k]))throw Error('검토 대상 내용이 바뀌었습니다. 검토 요청으로 다시 저장하세요.');
      }
      const out={...p,version:old.version+1};
      db.records[key]=out;
      const history=[{id:Date.now(),case_id:c.id,signal_id:s.id,at:new Date().toISOString(),actor:p.status==='검토 완료'?p.reviewer:p.performer,payload:JSON.stringify(p)},...db.history].slice(0,100);
      try {storage.setItem(KEY,JSON.stringify({records:db.records,history}));}
      catch {throw Error('이 브라우저에 저장할 수 없습니다. 저장 공간이나 브라우저 설정을 확인하세요.');}
      return out;
    }
    function exportText(caseId) {
      const db=read(),c=db.cases.find(c=>c.id===caseId);
      if(!c)throw Error('알 수 없는 업무입니다.');
      const labels=['수행자','검토자','요청 자료','선택 절차','선택 이유','증거 참조','실제 수행 결과','작성자 결론','미해결 사항','검토 의견','업무 상태'];
      const lines=['계속기업 검토 조서 초안 — 시연용','가상자료 / 감사판단 및 실제 수행 사실을 증명하는 문서가 아님',`기업: ${c.name} | 2025년 | 별도 | 금액 단위: 백만원`,'기준 원문: 공식 적용본 대조 전, 연결 보류','AI: 미연결, 고정된 절차 예시 사용','저장 위치: 현재 기기·브라우저 / 팀 공동 기록 아님',''];
      for(const s of c.signals){const r=db.records[c.id+':'+s.id];lines.push(`[${s.title}]`,`발견: ${s.value}`,`판정: ${s.flag===null?'자료 부족':s.flag?'추가 검토 필요':'해당 신호 미검출'}`,`근거: ${s.source}`,`점검 규칙: ${s.rule}`,...FIELDS.map((k,i)=>`${labels[i]}: ${r[k]||'미입력'}`),`저장 버전: ${r.version}`,'');}
      return lines.join('\n');
    }
    async function request(path, options={}) {
      try {
        if(path==='/api/state')return {ok:true,json:async()=>read()};
        if(path==='/api/save'&&options.method==='POST')return {ok:true,json:async()=>save(JSON.parse(options.body))};
        if(path.startsWith('/api/export?'))return {ok:true,text:async()=>exportText(new URLSearchParams(path.split('?')[1]).get('case'))};
        throw Error('지원하지 않는 요청입니다.');
      } catch(e) {return {ok:false,json:async()=>({error:e.message}),text:async()=>e.message};}
    }
    return {read,save,exportText,request};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={createDemo};
  else root.createAuditDemo=createDemo;
})(typeof window!=='undefined'?window:globalThis);
