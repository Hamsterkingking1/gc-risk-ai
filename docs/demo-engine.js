(function (root) {
  'use strict';
  const FIELDS=['performer','reviewer','requests','procedure','reason','evidence','result','conclusion','unresolved','review_note','status'];
  const STATUSES=['미착수','자료 요청','수행 중','검토 요청','검토 완료'];
  const KEY='gc-audit-demo-v1';
  const CUSTOM_KEY='gc-audit-custom-cases-v1';
  const BASE_RULES=[
    {
      id:'loss',title:'반복 손실',rule:'최근 3개년 당기순손익이 모두 음수',
      why:'손실의 지속 원인과 경영진의 손익 개선계획 실현 가능성을 확인합니다.',
      requests:'경영진 계속기업 평가서, 손익 개선계획 및 이사회 의사록, 결산 후 최근 월별 가결산 실적',
      procedure:'손실의 주요 원인을 고정비·원가율·일회성 비용으로 구분하고 개선계획의 가정을 최근 실적과 비교합니다.',
      standard_ref:'회계감사기준(KGA) 570 문단 A3 (재무적 사건 또는 상황: 반복적인 영업손실 및 당기순손실), 문단 16(경영진의 향후 대응계획 평가)',
      assignee_role:'담당 A · 손익/영업팀',
      team_tasks:[
        '수행담당(Staff A): 3개년 공시 손익계산서 계정별 증감 분석 및 영업손실·당기순손실 원인 분류표 작성',
        '수행담당(Staff B): 경영진 손익개선계획서(원가절감·비주력 사업 정리·판가 인상) 입수 및 보고기간 후 월별 가결산 실적과 대사',
        '검토자(In-Charge): 경영진 매출·이익률 회복 가정의 합리성 검토 및 조서 교차검토 의견 기록'
      ],
      procedure_templates:[
        {label:'[절차 1] 3개년 손익 악화 원인 분해 및 고정비 커버리지 검토',text:'1) 3개년 매출원가율·판관비 추이를 대사하여 손실 원인을 영업 구조적 요인과 일회성 요인으로 구분함.\n2) 공헌이익률 기준 손익분기점(BEP) 매출액을 재계산하고 당기 달성률과 비교함.'},
        {label:'[절차 2] 경영진 손익개선계획과 결산 후 실제 실적 대사 (KGA 570.16)',text:'1) 경영진이 제시한 차기 손익개선계획 및 이사회 보고자료를 입수함.\n2) 보고기간 종료일 이후 최근 월차 가결산 손익 및 수주잔고 명세와 비교하여 계획 달성 가능성을 검증함.'},
        {label:'[절차 3] 영업용 자산(유·무형자산) 손상징후 연계 검토',text:'1) 3년 연속 손실 발생 사업부문의 현금창출단위(CGU) 손상검토 대상 포함 여부를 확인함.\n2) 사용가치 평가 시 적용된 할인율과 매출 성장률 가정이 계속기업 평가 가정과 일관되는지 대사함.'}
      ]
    },
    {
      id:'cash',title:'영업현금흐름 악화',rule:'최근 3개년 영업현금흐름이 모두 음수',
      why:'영업에서 필요한 현금을 창출할 수 있는지와 향후 12개월 자금수지 충족 여부를 검토합니다.',
      requests:'향후 12개월 월별 자금수지계획(Cash Flow Forecast), 기초 현금잔액 증빙, 매출채권 회수 일정표',
      procedure:'자금계획 시작 잔액을 실제 예금잔액과 대사하고 매출·회수 가정과 실제 실적의 차이를 확인합니다.',
      standard_ref:'회계감사기준(KGA) 570 문단 A3 (부의 영업현금흐름), 문단 16(c) (현금흐름 예측의 신뢰성 및 기초 가정의 타당성 평가)',
      assignee_role:'담당 B · 자금/현금흐름팀',
      team_tasks:[
        '수행담당(Staff B): 향후 12개월 월별 자금수지계획표 입수 및 기초 현금및현금성자산 잔액의 은행조회서·원장 대사',
        '수행담당(Staff C): 영업현금 유입 가정(매출채권 회수율)과 유출 가정(매입채무·급여·이자 지급)의 과거 실적 대비 민감도 분석 수행',
        '검토자(In-Charge): 보수적 시나리오(매출 10~20% 하향) 하에서 자금 부족 발생 시점 및 가용 유동성 한도 교차검토'
      ],
      procedure_templates:[
        {label:'[절차 1] 향후 12개월 월별 자금수지계획 기초잔액 및 산식 검증 (KGA 570.16c)',text:'1) 경영진의 향후 12개월 월별 자금수지계획표를 입수하고 산술적 정확성을 재계산함.\n2) 기초 가용현금 잔액을 결산일 예금잔액증명서 및 사용제한 예금(질권설정 등) 명세와 대사하여 실제 인출 가능액을 확인함.'},
        {label:'[절차 2] 영업현금 유출입 가정의 역사적 정확성 및 민감도 분석',text:'1) 전기 자금계획 대비 당기 실제 현금흐름 달성률을 비교하여 경영진 예측 편향 여부를 확인함.\n2) 매출 수금 지연 또는 원재료비 상승 시나리오를 적용한 스트레스 테스트를 수행하여 월별 최저 현금잔액이 음수(-)로 전환되는지 점검함.'},
        {label:'[절차 3] 운전자본(매출채권·재고자산) 현금화 가능성 대사',text:'1) 영업현금 유입에 반영된 주요 거래처 매출채권의 연령분석표와 보고기간 후 실제 입금내역을 대사함.\n2) 장기체화 재고자산의 현금 유입 반영 여부를 확인하여 과대계상된 유입액을 차감함.'}
      ]
    },
    {
      id:'liquidity',title:'유동성 저하',rule:'당기 유동비율 < 100% (유동자산 ÷ 유동부채 × 100)',
      why:'순유동부채(유동부채 초과) 상태에서 단기 지급 의무에 대응할 재원과 회수 가능성을 확인합니다.',
      requests:'유동자산·유동부채 계정별 명세서, 사용제한 금융상품 명세, 단기 지급 일정표 및 자금조달 계획',
      procedure:'유동자산의 회수 예상 시점과 유동부채 지급 일정을 비교하고 부족 자금의 조달 근거를 확인합니다.',
      standard_ref:'회계감사기준(KGA) 570 문단 A3 (순유동부채 또는 순부채 상태, 주요 재무비율 악화), 문단 16(b)',
      assignee_role:'담당 C · 유동성/운전자본팀',
      team_tasks:[
        '수행담당(Staff C): 유동자산 중 즉시 현금화가 어려운 자산(담보제공 예금, 대손우려 채권, 불용재고) 발췌 및 실질 가용유동성 산출',
        '수행담당(Staff A): 유동부채 중 향후 3~6개월 내 만기 도래하는 매입채무·미지급금·단기차입금 지급 스케줄 대사',
        '검토자(In-Charge): 유동부채가 유동자산을 초과하는 금액에 대한 외부 자금조달(유상증자, 자산매각 등) 증빙의 실행 가능성 검토'
      ],
      procedure_templates:[
        {label:'[절차 1] 실질 가용 유동자산 재산정 및 사용제한 자산 차감',text:'1) 유동자산 내 현금및현금성자산·단기금융상품 중 차입금 담보(질권) 설정액을 금융기관조회서와 대사하여 가용유동성에서 제외함.\n2) 회수 기일이 경과한 매출채권 및 진부화 재고자산을 제외한 실질 단기 회수 가능액을 산출함.'},
        {label:'[절차 2] 단기 지급의무 만기 스케줄과 회수 시점 매칭',text:'1) 결산일 기준 유동부채를 만기 구간별(1개월, 3개월, 6개월, 12개월)로 분류하고 유동자산 회수 예정 시점과 매칭함.\n2) 연체 중인 매입채무·세금·급여 등 우선 변제 채무 존재 여부를 원장 및 결산 후 출금내역으로 확인함.'},
        {label:'[절차 3] 비영업자산 매각 및 자본확충 계획의 실행 가능성 확인',text:'1) 유동성 부족 해소를 위해 계획된 유형자산·투자자산 매각 건의 이사회 결의서, 매매계약서 및 감정평가서를 확인함.\n2) 유상증자 등 자본조달 계획의 경우 납입 확약서 또는 공시 내역 등 객관적 증거를 확인함.'}
      ]
    },
    {
      id:'debt',title:'차입금 상환 부담',rule:'1년 이내 만기도래 차입금 ÷ 총차입금 ≥ 50%',
      why:'차입금 만기 집중과 상환·차환(만기연장) 계획의 실행 가능성 및 약정사항 준수 여부를 확인합니다.',
      requests:'차입금·사채 만기 상환 스케줄표, 대출 약정서(재무약정 포함), 금융기관 만기연장 협의 자료',
      procedure:'만기표를 계약서·금융기관조회서와 대사하고 상환 재원 및 만기연장 계획의 뒷받침 자료를 확인합니다.',
      standard_ref:'회계감사기준(KGA) 570 문단 A3 (만기가 도래하는 고정차입금에 대한 갱신이나 상환의 현실적 가능성 부재, 차입약정 위반)',
      assignee_role:'담당 D · 차입금/약정검토팀',
      team_tasks:[
        '수행담당(Staff D): 단기차입금·유동성장기차입금·사채 명세를 금융기관조회서 및 대출계약서와 대사하여 1년 내 만기 집중도 확인',
        '수행담당(Staff B): 차입약정서상 재무비율 유지 조건(Covenants) 및 기한이익상실(EOD) 사유 발생 여부, 조기상환청구권(Put Option) 행사일 확인',
        '검토자(In-Charge): 보고기간 후 만기 도래분의 실제 연장(Roll-over)·상환 내역 확인 및 미확정 차환 계획의 감사증거 충분성 검토'
      ],
      procedure_templates:[
        {label:'[절차 1] 단기차입금·유동성장기부채 만기표 및 금융기관조회서 대사',text:'1) 결산일 현재 단기차입금·유동성장기차입금·유동성사채 명세를 금융기관조회서 및 약정서와 전수 대사함.\n2) 전환사채(CB)·신주인수권부사채(BW)의 조기상환청구권(Put Option) 도래 시점과 행사가능 금액을 유동부채 분류 기준과 비교함.'},
        {label:'[절차 2] 보고기간 후 차입금 만기연장(Roll-over) 및 상환 증빙 확인',text:'1) 결산일 이후 감사보고서일 사이에 만기가 도래한 차입금의 실제 상환 또는 만기연장 승인서·변경계약서를 확인함.\n2) 향후 만기 도래 예정 차입금에 대한 금융기관과의 연장 협의 진행 상황 및 담보 여력을 점검함.'},
        {label:'[절차 3] 차입약정(Covenants) 위반 및 기한이익상실(EOD) 여부 점검',text:'1) 주요 차입 약정서상 부채비율·이자보상배율 등 재무약정 조건 준수 여부를 재계산함.\n2) 약정 위반 시 즉시 상환 의무 발생 여부 및 결산일 이전 면제(Waiver) 확약서 수취 여부를 확인함.'}
      ]
    },
    {
      id:'wording',title:'계속기업 관련 문구',rule:'전기 보고서 관련 문구 존재 여부 (DART 공시 감사의견·강조사항 또는 사전 입력값)',
      why:'전기 계속기업 불확실성 문구의 대상 상황이 당기에 해소되었는지와 당기 공시 적정성을 확인합니다.',
      requests:'전기·당기 감사보고서, 당기 경영진 계속기업 평가서, 당기 재무제표 주석(계속기업) 초안',
      procedure:'전기 문구의 대상 상황과 당기 변화를 비교하고, 당기 주석 공시 및 감사보고서 강조사항 반영 여부를 검토합니다.',
      standard_ref:'회계감사기준(KGA) 570 문단 18~23 (중요한 불확실성이 존재하는 경우 주석 공시의 적정성 평가 및 감사보고서 별도 단락 기재)',
      assignee_role:'담당 E · 공시/보고서팀 (In-Charge)',
      team_tasks:[
        '수행담당(Staff E): 전기 감사보고서 강조사항(계속기업 관련 중요한 불확실성) 및 재무제표 주석 원문 발췌·당기 해소 여부 비교표 작성',
        '수행담당(Staff A): 당기 재무제표 주석 초안에 불확실성 유발 사건과 경영진 대응계획이 구체적으로 공시되었는지(KGA 570.19) 대사',
        '검토자(In-Charge/업무수행이사): 계속기업 가정의 타당성 및 감사보고서 강조사항(계속기업 관련 중요한 불확실성) 문단 기재 여부 최종 검토'
      ],
      procedure_templates:[
        {label:'[절차 1] 전기 계속기업 불확실성 원인 사항의 당기 변화 추적',text:'1) 전기 감사보고서 강조사항 및 주석에 기재된 계속기업 불확실성 요인(손실, 유동성 부족 등)을 항목별로 발췌함.\n2) 각 요인에 대한 당기 중 경영진 자구계획 이행 실적(유상증자, 차입금 상환, 사업 구조조정 등)과 미해소 사유를 대사함.'},
        {label:'[절차 2] 당기 재무제표 계속기업 주석 공시의 적정성 검토 (KGA 570.19)',text:'1) 당기 재무제표 주석 초안에 중요한 의문을 초래하는 주요 사건·상황과 경영진의 대응계획이 명확히 기술되었는지 확인함.\n2) 정상적인 영업과정에서 자산 회수 및 부채 상환이 불가능할 수 있다는 사실이 명시되었는지 점검함.'},
        {label:'[절차 3] 경영진 확인서 수취 및 감사보고서 강조사항 문단 검토 (KGA 570.16e/22)',text:'1) 경영진으로부터 향후 대응계획과 그 실행 가능성에 대한 서면진술(경영진확인서)을 수취함.\n2) 주석 공시가 적정한 경우 감사보고서에 [계속기업 관련 중요한 불확실성] 별도 단락을 추가하고 주석 참조를 명시할지 검토함.'}
      ]
    }
  ];

  function computeSignals(c) {
    const years=c.years||[2023,2024,2025], unit=c.unit||'백만원';
    const fmt=n=>n===null||n===undefined||Number.isNaN(n)?'자료 없음':Number(n).toLocaleString('ko-KR');
    const values=[];
    for(const key of ['profit','cash']) {
      const xs=c[key]||[null,null,null];
      const anyNull=xs.some(x=>x===null||x===undefined||Number.isNaN(x));
      values.push([anyNull?null:xs.every(x=>x<0), years.map((y,i)=>`${y}: ${fmt(xs[i])}`).join(' / ')+` (${unit})`]);
    }
    const a=c.assets,b=c.liabilities;
    const lRatio=(a!==null&&b!==null&&b>0)?(a/b*100):null;
    values.push([lRatio===null?null:lRatio<100, lRatio===null?'계산 보류':`${fmt(a)} ÷ ${fmt(b)} × 100 = ${lRatio.toFixed(1)}%`]);
    const due=c.due,debt=c.debt;
    const dRatio=(due!==null&&debt!==null&&debt>0&&due>=0&&due<=debt)?(due/debt*100):null;
    values.push([dRatio===null?null:dRatio>=50, dRatio===null?'계산 보류':`${fmt(due)} ÷ ${fmt(debt)} × 100 = ${dRatio.toFixed(1)}%`]);
    const w=c.wording;
    values.push([w===undefined?null:w, w===null||w===undefined?'원문 미확보':`전기 감사보고서: ${w?'관련 문구 있음':'관련 문구 없음'}`]);
    return BASE_RULES.map((r,i)=>({
      ...r,
      flag:values[i][0],
      value:values[i][1],
      source:`사용자 직접 입력 재무제표 / ${c.name} / ${i<2?'2023~2025년 손익·현금흐름표':i<4?'2025년 재무상태·차입금 명세':'전기 감사보고서 강조사항 여부'}`,
      standard_status:'공식 적용본 대조 전 · 기준 연결 보류'
    }));
  }

  function createDemo(baseCases, storage) {
    const clone=x=>JSON.parse(JSON.stringify(x));
    function initialRecord(s) {
      return {...Object.fromEntries(FIELDS.map(k=>[k,''])),requests:s.requests,procedure:s.procedure,status:'미착수',version:0};
    }
    function allCases() {
      let custom=[];
      try {
        const raw=storage.getItem(CUSTOM_KEY);
        if(raw) custom=JSON.parse(raw)||[];
      } catch { custom=[]; }
      return [...clone(baseCases), ...custom.map(c=>({...c,signals:computeSignals(c)}))];
    }
    function read() {
      const raw=storage.getItem(KEY);
      let saved;
      try { saved=raw?JSON.parse(raw):{records:{},history:[]}; }
      catch { throw Error('저장 기록을 읽을 수 없습니다. 브라우저 데이터를 지우기 전에 기록을 확인해주세요.'); }
      if(!saved||!saved.records||!Array.isArray(saved.history))throw Error('저장 기록 형식이 올바르지 않습니다.');
      const cases=allCases();
      const records={};
      for(const c of cases)for(const s of c.signals)records[c.id+':'+s.id]={...initialRecord(s),...(saved.records[c.id+':'+s.id]||{})};
      return {cases,records,history:saved.history};
    }
    function addCustomCase(input) {
      const name=String(input.name||'').trim();
      if(!name) throw Error('기업명을 입력하세요.');
      const num=v=>{const s=String(v??'').replace(/,/g,'').trim();if(s===''||s==='-')return null;const n=Number(s);return Number.isFinite(n)?Math.round(n):null;};
      const customCase={
        id:'custom_'+Date.now(),
        name,
        custom:true,
        fs_label:input.fs_label||'별도',
        unit:'백만원',
        years:[2023,2024,2025],
        profit:[num(input.profit_2023),num(input.profit_2024),num(input.profit_2025)],
        cash:[num(input.cash_2023),num(input.cash_2024),num(input.cash_2025)],
        assets:num(input.assets),
        liabilities:num(input.liabilities),
        debt:num(input.debt),
        due:num(input.due),
        wording:input.wording==='true'?true:input.wording==='false'?false:null
      };
      let list=[];
      try { list=JSON.parse(storage.getItem(CUSTOM_KEY)||'[]')||[]; } catch { list=[]; }
      list.push(customCase);
      storage.setItem(CUSTOM_KEY,JSON.stringify(list));
      return {...customCase,signals:computeSignals(customCase)};
    }
    function save(data) {
      const cases=allCases();
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
      const lines=['계속기업 검토 조서 초안 — 시연용','가상자료 / 감사판단 및 실제 수행 사실을 증명하는 문서가 아님',`기업: ${c.name} | 2025년 | ${c.fs_label||'별도'} | 금액 단위: ${c.unit||'백만원'}`,'기준 원문: 공식 적용본 대조 전, 연결 보류','AI: 미연결, 고정된 절차 예시 사용','저장 위치: 현재 기기·브라우저 / 팀 공동 기록 아님',''];
      for(const s of c.signals){const r=db.records[c.id+':'+s.id];lines.push(`[${s.title}] (${s.assignee_role||''})`,`발견: ${s.value}`,`판정: ${s.flag===null?'자료 부족':s.flag?'비정상 · 추가 검토 필요':'정상 · 해당 신호 미검출'}`,`근거: ${s.source}`,`점검 규칙: ${s.rule}`,`참조 기준: ${s.standard_ref||''}`,...FIELDS.map((k,i)=>`${labels[i]}: ${r[k]||'미입력'}`),`저장 버전: ${r.version}`,'');}
      return lines.join('\n');
    }
    async function request(path, options={}) {
      try {
        if(path==='/api/state')return {ok:true,json:async()=>read()};
        if(path==='/api/save'&&options.method==='POST')return {ok:true,json:async()=>save(JSON.parse(options.body))};
        if(path==='/api/custom-case'&&options.method==='POST')return {ok:true,json:async()=>addCustomCase(JSON.parse(options.body))};
        if(path.startsWith('/api/export?'))return {ok:true,text:async()=>exportText(new URLSearchParams(path.split('?')[1]).get('case'))};
        throw Error('지원하지 않는 요청입니다.');
      } catch(e) {return {ok:false,json:async()=>({error:e.message}),text:async()=>e.message};}
    }
    return {read,save,addCustomCase,exportText,request};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={createDemo};
  else root.createAuditDemo=createDemo;
})(typeof window!=='undefined'?window:globalThis);
