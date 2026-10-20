(function(root){
  'use strict';
  const VERSION='gc-risk-quality-1';
  function won(value,unit='원'){
    if(value===null||value===undefined||typeof value==='boolean')return null;
    let s=String(value).trim();
    if(s.startsWith('(')&&s.endsWith(')'))s='-'+s.slice(1,-1);
    const scale={원:1n,천원:1000n,백만원:1000000n,억원:100000000n}[unit];
    if(!scale||! /^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,6})?$/.test(s))return null;
    const clean=s.replaceAll(',',''),neg=clean.startsWith('-'),parts=clean.replace('-','').split('.');
    const fraction=parts[1]||'',denom=10n**BigInt(fraction.length);
    const n=(BigInt(parts[0])*denom+BigInt(fraction||'0'))*scale;
    return n%denom===0n?(neg?-n/denom:n/denom):null;
  }
  function enrich(c,signals){
    const ys=c.years||[],valid=ys.length===3&&ys.every((y,i)=>Number.isInteger(y)&&y===ys[0]+i);
    const exact=c.amounts_won;
    function vals(k){let v=(exact||c)[k];return (Array.isArray(v)?v:[v]).map(x=>won(x,exact?'원':c.unit||'백만원'));}
    const series=k=>{const v=vals(k);return valid&&v.length===3?v:[null,null,null];};
    const scalar=k=>{const v=vals(k);return valid&&v.length===1?v[0]:null;};
    const profit=series('profit'),cash=series('cash'),a=scalar('assets'),b=scalar('liabilities');
    let due=scalar('due'),debt=scalar('debt'),warnings=[];
    if(c.real&&!exact)warnings.push('기존 백만원 반올림 자료: 원 단위 재수집 전에는 작은 금액·경계값 검증이 제한됩니다.');
    if(!valid)warnings.push('연속된 3개 사업연도를 확인할 수 없습니다.');
    if(c.custom)warnings.push('사용자 입력 자료: 공시 원문과 단위·연결/별도 기준을 대조해야 합니다.');
    let missing=[];
    if(c.real){
      const ac=c.accounts_used?.[ys.at(-1)]||{};
      missing=[...new Set(['st_borrow','cur_lt_borrow','cur_bonds','lt_borrow','bonds'].filter(k=>!ac[k]).concat(c.debt_missing||[]))];
      if(missing.length)due=debt=null;
    }
    const allneg=xs=>xs.includes(null)?null:xs.every(v=>v<0n);
    const flags=[allneg(profit),cash[2]===null?null:cash[2]<0n,
      a===null||b===null||a<0n||b<=0n?null:a<b,
      due===null||debt===null||due<0n||debt<=0n||due>debt?null:due*2n>=debt,
      typeof c.wording==='boolean'?c.wording:null];
    const fmt=x=>x===null?'자료 없음':x.toLocaleString('ko-KR')+'원';
    const tri=x=>x===null?'미확인':x?'해당':'미해당';
    const detail=`당기 음수: ${tri(flags[1])} / 최근 2년 연속 음수: ${tri(allneg(cash.slice(-2)))} / 3년 연속 음수: ${tri(allneg(cash))}`;
    const ratio=(a,b)=>{const v=(a*10000n+b/2n)/b;return `${v/100n}.${String(v%100n).padStart(2,'0')}`;};
    const texts=[ys.map((y,i)=>`${y}: ${fmt(profit[i])}`).join(' / '),
      ys.map((y,i)=>`${y}: ${fmt(cash[i])}`).join(' / ')+' · '+detail,
      flags[2]===null?'계산 보류: 유동자산·유동부채 확인 필요':`${fmt(a)} ÷ ${fmt(b)} × 100 = ${ratio(a,b)}%`,
      flags[3]===null?'계산 보류: 차입금 구성계정의 누락·범위 확인 필요':`${fmt(due)} ÷ ${fmt(debt)} × 100 = ${ratio(due,debt)}%`,
      flags[4]===null?'원문 확인 필요':`전기 요약 문구 ${flags[4]?'검출':'미검출'} · 원문 전체 판단 아님`];
    if(c.integrity_errors?.length){
      warnings.push(...c.integrity_errors);
      for(let i=0;i<4;i++){flags[i]=null;texts[i]='판정 보류: 저장 원본과 금액의 일치 여부를 확인하세요.';}
    }
    return signals.map((s,i)=>{
      const r={...s,flag:flags[i],value:texts[i],rule_version:VERSION,data_warnings:[...warnings],
        procedure_status:'미검토 제안 · 실제 수행 아님',
        provenance:{company:c.name,years:ys,basis:c.fs_label,unit:c.unit,fetched_at:c.fetched_at,
          receipt_numbers:c.rcept_nos||{},accounts:c.accounts_used||{},source_hashes:c.source_hashes||{},
          review_status:'원문 및 회계적 의미 대조 필요'}};
      if(i===1){r.coverage=cash.includes(null)?'partial':'complete';r.rule='당기 영업현금흐름 < 0 · 최근 2년/3년 연속 음수는 별도 표시';if(cash.includes(null))r.data_warnings.push('비교연도 자료 부족: 연속 음수 여부를 확인하세요.');}
      if(i===4&&c.wording_detail?.prior_text)r.value+=' · '+c.wording_detail.prior_text;
      if(i===3&&missing.length)r.data_warnings.push('미확인 차입금 계정: '+missing.map(k=>({st_borrow:'단기차입금',cur_lt_borrow:'유동성장기차입금',cur_bonds:'유동성사채',lt_borrow:'장기차입금',bonds:'사채'}[k]||k)).join(', '));
      if(c.custom)r.source='사용자 직접 입력 / '+c.name+' / 원문 대조 전';
      return r;
    });
  }
  const api={won,enrich,VERSION};
  if(typeof module!=='undefined')module.exports=api;
  root.GCQuality=api;
})(typeof globalThis!=='undefined'?globalThis:this);
