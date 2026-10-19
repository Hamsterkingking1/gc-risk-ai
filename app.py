"""Local & DART-backed Going Concern Audit Workflow Prototype. Python standard library only."""
import json
import os
import sqlite3
import threading
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'audit.sqlite3'
HOST, PORT = '127.0.0.1', int(os.environ.get('GC_AUDIT_PORT', '8765'))

SYNTHETIC_CASES = [
    dict(id='risk', name='가상 A제조', years=[2023,2024,2025], profit=[-100,-80,-120], cash=[-60,-90,-110], assets=650, liabilities=1000, debt=800, due=500, wording=True),
    dict(id='clear', name='가상 B제조', years=[2023,2024,2025], profit=[100,130,160], cash=[80,110,140], assets=1800, liabilities=1000, debt=800, due=200, wording=False),
    dict(id='missing', name='가상 C제조', years=[2023,2024,2025], profit=[-100,None,-50], cash=[-60,None,-110], assets=650, liabilities=None, debt=None, due=300, wording=None),
]

def load_real_cases(folder=ROOT / 'cases'):
    """dart_fetch.py가 만든 공개 공시 스냅샷을 불러옵니다. 형식이 잘못된 파일은 건너뜁니다."""
    out = []
    for path in sorted(folder.glob('real_*.json')) if folder.exists() else []:
        try:
            case = json.loads(path.read_text(encoding='utf-8'))
            if all(k in case for k in ('id', 'name', 'years', 'profit', 'cash', 'assets', 'liabilities', 'debt', 'due', 'wording')):
                out.append(case)
        except (OSError, ValueError):
            continue
    return out

CASES = load_real_cases()

RULES = [
    dict(
        id='loss',
        title='반복 손실',
        rule='최근 3개년 당기순손익이 모두 음수',
        why='손실의 지속 원인과 경영진의 손익 개선계획 실현 가능성을 확인합니다.',
        requests='경영진 계속기업 평가서, 손익 개선계획 및 이사회 의사록, 결산 후 최근 월별 가결산 실적',
        procedure='손실의 주요 원인을 고정비·원가율·일회성 비용으로 구분하고 개선계획의 가정을 최근 실적과 비교합니다.',
        standard_ref='회계감사기준(KGA) 570 문단 A3 (재무적 사건 또는 상황: 반복적인 영업손실 및 당기순손실), 문단 16(경영진의 향후 대응계획 평가)',
        assignee_role='담당 A · 손익/영업팀',
        team_tasks=[
            '수행담당(Staff A): 3개년 공시 손익계산서 계정별 증감 분석 및 영업손실·당기순손실 원인 분류표 작성',
            '수행담당(Staff B): 경영진 손익개선계획서(원가절감·비주력 사업 정리·판가 인상) 입수 및 보고기간 후 월별 가결산 실적과 대사',
            '검토자(In-Charge): 경영진 매출·이익률 회복 가정의 합리성 검토 및 조서 교차검토 의견 기록'
        ],
        procedure_templates=[
            dict(label='[절차 1] 3개년 손익 악화 원인 분해 및 고정비 커버리지 검토', text='1) 3개년 매출원가율·판관비 추이를 대사하여 손실 원인을 영업 구조적 요인과 일회성 요인으로 구분함.\n2) 공헌이익률 기준 손익분기점(BEP) 매출액을 재계산하고 당기 달성률과 비교함.'),
            dict(label='[절차 2] 경영진 손익개선계획과 결산 후 실제 실적 대사 (KGA 570.16)', text='1) 경영진이 제시한 차기 손익개선계획 및 이사회 보고자료를 입수함.\n2) 보고기간 종료일 이후 최근 월차 가결산 손익 및 수주잔고 명세와 비교하여 계획 달성 가능성을 검증함.'),
            dict(label='[절차 3] 영업용 자산(유·무형자산) 손상징후 연계 검토', text='1) 3년 연속 손실 발생 사업부문의 현금창출단위(CGU) 손상검토 대상 포함 여부를 확인함.\n2) 사용가치 평가 시 적용된 할인율과 매출 성장률 가정이 계속기업 평가 가정과 일관되는지 대사함.')
        ]
    ),
    dict(
        id='cash',
        title='영업현금흐름 악화',
        rule='최근 3개년 영업현금흐름이 모두 음수',
        why='영업에서 필요한 현금을 창출할 수 있는지와 향후 12개월 자금수지 충족 여부를 검토합니다.',
        requests='향후 12개월 월별 자금수지계획(Cash Flow Forecast), 기초 현금잔액 증빙, 매출채권 회수 일정표',
        procedure='자금계획 시작 잔액을 실제 예금잔액과 대사하고 매출·회수 가정과 실제 실적의 차이를 확인합니다.',
        standard_ref='회계감사기준(KGA) 570 문단 A3 (부의 영업현금흐름), 문단 16(c) (현금흐름 예측의 신뢰성 및 기초 가정의 타당성 평가)',
        assignee_role='담당 B · 자금/현금흐름팀',
        team_tasks=[
            '수행담당(Staff B): 향후 12개월 월별 자금수지계획표 입수 및 기초 현금및현금성자산 잔액의 은행조회서·원장 대사',
            '수행담당(Staff C): 영업현금 유입 가정(매출채권 회수율)과 유출 가정(매입채무·급여·이자 지급)의 과거 실적 대비 민감도 분석 수행',
            '검토자(In-Charge): 보수적 시나리오(매출 10~20% 하향) 하에서 자금 부족 발생 시점 및 가용 유동성 한도 교차검토'
        ],
        procedure_templates=[
            dict(label='[절차 1] 향후 12개월 월별 자금수지계획 기초잔액 및 산식 검증 (KGA 570.16c)', text='1) 경영진의 향후 12개월 월별 자금수지계획표를 입수하고 산술적 정확성을 재계산함.\n2) 기초 가용현금 잔액을 결산일 예금잔액증명서 및 사용제한 예금(질권설정 등) 명세와 대사하여 실제 인출 가능액을 확인함.'),
            dict(label='[절차 2] 영업현금 유출입 가정의 역사적 정확성 및 민감도 분석', text='1) 전기 자금계획 대비 당기 실제 현금흐름 달성률을 비교하여 경영진 예측 편향 여부를 확인함.\n2) 매출 수금 지연 또는 원재료비 상승 시나리오를 적용한 스트레스 테스트를 수행하여 월별 최저 현금잔액이 음수(-)로 전환되는지 점검함.'),
            dict(label='[절차 3] 운전자본(매출채권·재고자산) 현금화 가능성 대사', text='1) 영업현금 유입에 반영된 주요 거래처 매출채권의 연령분석표와 보고기간 후 실제 입금내역을 대사함.\n2) 장기체화 재고자산의 현금 유입 반영 여부를 확인하여 과대계상된 유입액을 차감함.')
        ]
    ),
    dict(
        id='liquidity',
        title='유동성 저하',
        rule='당기 유동비율 < 100% (유동자산 ÷ 유동부채 × 100)',
        why='순유동부채(유동부채 초과) 상태에서 단기 지급 의무에 대응할 재원과 회수 가능성을 확인합니다.',
        requests='유동자산·유동부채 계정별 명세서, 사용제한 금융상품 명세, 단기 지급 일정표 및 자금조달 계획',
        procedure='유동자산의 회수 예상 시점과 유동부채 지급 일정을 비교하고 부족 자금의 조달 근거를 확인합니다.',
        standard_ref='회계감사기준(KGA) 570 문단 A3 (순유동부채 또는 순부채 상태, 주요 재무비율 악화), 문단 16(b)',
        assignee_role='담당 C · 유동성/운전자본팀',
        team_tasks=[
            '수행담당(Staff C): 유동자산 중 즉시 현금화가 어려운 자산(담보제공 예금, 대손우려 채권, 불용재고) 발췌 및 실질 가용유동성 산출',
            '수행담당(Staff A): 유동부채 중 향후 3~6개월 내 만기 도래하는 매입채무·미지급금·단기차입금 지급 스케줄 대사',
            '검토자(In-Charge): 유동부채가 유동자산을 초과하는 금액에 대한 외부 자금조달(유상증자, 자산매각 등) 증빙의 실행 가능성 검토'
        ],
        procedure_templates=[
            dict(label='[절차 1] 실질 가용 유동자산 재산정 및 사용제한 자산 차감', text='1) 유동자산 내 현금및현금성자산·단기금융상품 중 차입금 담보(질권) 설정액을 금융기관조회서와 대사하여 가용유동성에서 제외함.\n2) 회수 기일이 경과한 매출채권 및 진부화 재고자산을 제외한 실질 단기 회수 가능액을 산출함.'),
            dict(label='[절차 2] 단기 지급의무 만기 스케줄과 회수 시점 매칭', text='1) 결산일 기준 유동부채를 만기 구간별(1개월, 3개월, 6개월, 12개월)로 분류하고 유동자산 회수 예정 시점과 매칭함.\n2) 연체 중인 매입채무·세금·급여 등 우선 변제 채무 존재 여부를 원장 및 결산 후 출금내역으로 확인함.'),
            dict(label='[절차 3] 비영업자산 매각 및 자본확충 계획의 실행 가능성 확인', text='1) 유동성 부족 해소를 위해 계획된 유형자산·투자자산 매각 건의 이사회 결의서, 매매계약서 및 감정평가서를 확인함.\n2) 유상증자 등 자본조달 계획의 경우 납입 확약서 또는 공시 내역 등 객관적 증거를 확인함.')
        ]
    ),
    dict(
        id='debt',
        title='차입금 상환 부담',
        rule='1년 이내 만기도래 차입금 ÷ 총차입금 ≥ 50%',
        why='차입금 만기 집중과 상환·차환(만기연장) 계획의 실행 가능성 및 약정사항 준수 여부를 확인합니다.',
        requests='차입금·사채 만기 상환 스케줄표, 대출 약정서(재무약정 포함), 금융기관 만기연장 협의 자료',
        procedure='만기표를 계약서·금융기관조회서와 대사하고 상환 재원 및 만기연장 계획의 뒷받침 자료를 확인합니다.',
        standard_ref='회계감사기준(KGA) 570 문단 A3 (만기가 도래하는 고정차입금에 대한 갱신이나 상환의 현실적 가능성 부재, 차입약정 위반)',
        assignee_role='담당 D · 차입금/약정검토팀',
        team_tasks=[
            '수행담당(Staff D): 단기차입금·유동성장기차입금·사채 명세를 금융기관조회서 및 대출계약서와 대사하여 1년 내 만기 집중도 확인',
            '수행담당(Staff B): 차입약정서상 재무비율 유지 조건(Covenants) 및 기한이익상실(EOD) 사유 발생 여부, 조기상환청구권(Put Option) 행사일 확인',
            '검토자(In-Charge): 보고기간 후 만기 도래분의 실제 연장(Roll-over)·상환 내역 확인 및 미확정 차환 계획의 감사증거 충분성 검토'
        ],
        procedure_templates=[
            dict(label='[절차 1] 단기차입금·유동성장기부채 만기표 및 금융기관조회서 대사', text='1) 결산일 현재 단기차입금·유동성장기차입금·유동성사채 명세를 금융기관조회서 및 약정서와 전수 대사함.\n2) 전환사채(CB)·신주인수권부사채(BW)의 조기상환청구권(Put Option) 도래 시점과 행사가능 금액을 유동부채 분류 기준과 비교함.'),
            dict(label='[절차 2] 보고기간 후 차입금 만기연장(Roll-over) 및 상환 증빙 확인', text='1) 결산일 이후 감사보고서일 사이에 만기가 도래한 차입금의 실제 상환 또는 만기연장 승인서·변경계약서를 확인함.\n2) 향후 만기 도래 예정 차입금에 대한 금융기관과의 연장 협의 진행 상황 및 담보 여력을 점검함.'),
            dict(label='[절차 3] 차입약정(Covenants) 위반 및 기한이익상실(EOD) 여부 점검', text='1) 주요 차입 약정서상 부채비율·이자보상배율 등 재무약정 조건 준수 여부를 재계산함.\n2) 약정 위반 시 즉시 상환 의무 발생 여부 및 결산일 이전 면제(Waiver) 확약서 수취 여부를 확인함.')
        ]
    ),
    dict(
        id='wording',
        title='계속기업 관련 문구',
        rule='전기 보고서 관련 문구 존재 여부 (DART 공시 감사의견·강조사항 또는 사전 입력값)',
        why='전기 계속기업 불확실성 문구의 대상 상황이 당기에 해소되었는지와 당기 공시 적정성을 확인합니다.',
        requests='전기·당기 감사보고서, 당기 경영진 계속기업 평가서, 당기 재무제표 주석(계속기업) 초안',
        procedure='전기 문구의 대상 상황과 당기 변화를 비교하고, 당기 주석 공시 및 감사보고서 강조사항 반영 여부를 검토합니다.',
        standard_ref='회계감사기준(KGA) 570 문단 18~23 (중요한 불확실성이 존재하는 경우 주석 공시의 적정성 평가 및 감사보고서 별도 단락 기재)',
        assignee_role='담당 E · 공시/보고서팀 (In-Charge)',
        team_tasks=[
            '수행담당(Staff E): 전기 감사보고서 강조사항(계속기업 관련 중요한 불확실성) 및 재무제표 주석 원문 발췌·당기 해소 여부 비교표 작성',
            '수행담당(Staff A): 당기 재무제표 주석 초안에 불확실성 유발 사건과 경영진 대응계획이 구체적으로 공시되었는지(KGA 570.19) 대사',
            '검토자(In-Charge/업무수행이사): 계속기업 가정의 타당성 및 감사보고서 강조사항(계속기업 관련 중요한 불확실성) 문단 기재 여부 최종 검토'
        ],
        procedure_templates=[
            dict(label='[절차 1] 전기 계속기업 불확실성 원인 사항의 당기 변화 추적', text='1) 전기 감사보고서 강조사항 및 주석에 기재된 계속기업 불확실성 요인(손실, 유동성 부족 등)을 항목별로 발췌함.\n2) 각 요인에 대한 당기 중 경영진 자구계획 이행 실적(유상증자, 차입금 상환, 사업 구조조정 등)과 미해소 사유를 대사함.'),
            dict(label='[절차 2] 당기 재무제표 계속기업 주석 공시의 적정성 검토 (KGA 570.19)', text='1) 당기 재무제표 주석 초안에 중요한 의문을 초래하는 주요 사건·상황과 경영진의 대응계획이 명확히 기술되었는지 확인함.\n2) 정상적인 영업과정에서 자산 회수 및 부채 상환이 불가능할 수 있다는 사실이 명시되었는지 점검함.'),
            dict(label='[절차 3] 경영진 확인서 수취 및 감사보고서 강조사항 문단 검토 (KGA 570.16e/22)', text='1) 경영진으로부터 향후 대응계획과 그 실행 가능성에 대한 서면진술(경영진확인서)을 수취함.\n2) 주석 공시가 적정한 경우 감사보고서에 [계속기업 관련 중요한 불확실성] 별도 단락을 추가하고 주석 참조를 명시할지 검토함.')
        ]
    ),
]
FIELDS = ('performer','reviewer','requests','procedure','reason','evidence','result','conclusion','unresolved','review_note','status')
STATUSES = ('미착수','자료 요청','수행 중','검토 요청','검토 완료')

def signals(case):
    values = []
    unit = case.get('unit', '백만원')
    for key in ('profit','cash'):
        xs = case[key]
        values.append((None if any(x is None for x in xs) else all(x < 0 for x in xs), ' / '.join(f'{year}: ' + ('자료 없음' if x is None else f'{x:,}') for year,x in zip(case['years'],xs)) + f' ({unit})'))
    a,b = case['assets'],case['liabilities']
    ratio = a/b*100 if a is not None and b is not None and b > 0 else None
    values.append((None if ratio is None else ratio < 100, '계산 보류' if ratio is None else f'{a:,} ÷ {b:,} × 100 = {ratio:.1f}%'))
    a,b = case['due'],case['debt']
    ratio = a/b*100 if a is not None and b is not None and b > 0 and 0 <= a <= b else None
    values.append((None if ratio is None else ratio >= 50, '계산 보류' if ratio is None else f'{a:,} ÷ {b:,} × 100 = {ratio:.1f}%'))
    if case.get('real'):
        d = case.get('wording_detail', {})
        text = '감사의견 자료 미확보' if case['wording'] is None else f'{d.get("prior_year")}년 감사보고서: ' + ('계속기업 관련 문구 있음' if case['wording'] else '관련 문구 없음')
        if d.get('prior_text'):
            text += f' — {d["prior_text"][:200]}'
        values.append((case['wording'], text))
        sources = case['sources']
    else:
        values.append((case['wording'], '원문 미확보' if case['wording'] is None else '가상 전기 보고서: ' + ('관련 문구 있음' if case['wording'] else '관련 문구 없음')))
        sources = [f'가상 데이터 / {case["name"]} / ' + ('2023~2025년 손익·현금흐름표' if i<2 else '2025년 재무상태·차입금 명세' if i<4 else '2024년 보고서 메타데이터') for i in range(5)]
    out = [{**r, 'flag':v[0], 'value':v[1], 'source':sources[i], 'standard_status':'공식 적용본 대조 전 · 기준 연결 보류'} for i,(r,v) in enumerate(zip(RULES,values))]
    if case.get('real'):
        out[3]['rule'] = '(단기차입금 + 유동성장기차입금 + 유동성사채) ÷ (위 합계 + 장기차입금 + 사채) ≥ 50% · 공시 계정 기준 근사치'
        out[4]['rule'] = '전기 사업보고서의 감사의견 항목(강조사항·특기사항 등)에 "계속기업"·"존속능력"·"중요한 불확실성" 포함 여부 · 키워드 검색이며 원문 확인 필요'
    return out

@contextmanager
def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS records (case_id TEXT, signal_id TEXT, payload TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(case_id, signal_id))')
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, case_id TEXT, signal_id TEXT, at TEXT, actor TEXT, payload TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS custom_cases (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

def all_cases(c=None):
    if c is None:
        with connect() as conn:
            return all_cases(conn)
    custom = [json.loads(r['payload']) for r in c.execute('SELECT payload FROM custom_cases ORDER BY rowid ASC')]
    return CASES + custom

def add_custom_case(data):
    name = str(data.get('name') or '').strip()
    if not name:
        raise ValueError('기업명을 입력하세요.')
    def num(v):
        s = str(v if v is not None else '').replace(',', '').strip()
        if s in ('', '-'):
            return None
        try:
            return round(float(s))
        except ValueError:
            return None
    w = data.get('wording')
    case = dict(
        id=f'custom_{int(datetime.now(timezone.utc).timestamp()*1000)}',
        name=name,
        custom=True,
        fs_label=str(data.get('fs_label') or '별도'),
        unit='백만원',
        years=[2023, 2024, 2025],
        profit=[num(data.get('profit_2023')), num(data.get('profit_2024')), num(data.get('profit_2025'))],
        cash=[num(data.get('cash_2023')), num(data.get('cash_2024')), num(data.get('cash_2025'))],
        assets=num(data.get('assets')),
        liabilities=num(data.get('liabilities')),
        debt=num(data.get('debt')),
        due=num(data.get('due')),
        wording=True if w == 'true' else False if w == 'false' else None,
    )
    with connect() as c:
        c.execute('INSERT INTO custom_cases VALUES (?,?)', (case['id'], json.dumps(case, ensure_ascii=False)))
    return {**case, 'signals': signals(case)}

def read_record(c, case_id, signal_id):
    row=c.execute('SELECT payload,version FROM records WHERE case_id=? AND signal_id=?',(case_id,signal_id)).fetchone()
    if row:
        return {**json.loads(row['payload']), 'version':row['version']}
    rule=next(r for r in RULES if r['id']==signal_id)
    return {**dict.fromkeys(FIELDS,''), 'requests':rule['requests'],'procedure':rule['procedure'],'status':'미착수','version':0}

def save_record(data):
    case_id, signal_id = data.get('case_id'), data.get('signal_id')
    case=next((x for x in all_cases() if x['id']==case_id),None)
    if case is None or signal_id not in {r['id'] for r in RULES}:
        raise ValueError('알 수 없는 업무 또는 신호입니다.')
    payload={k:str(data.get(k,'')).strip() for k in FIELDS}
    if any(len(v)>20000 for v in payload.values()):
        raise ValueError('입력 항목은 20,000자 이내로 작성하세요.')
    if payload['status'] not in STATUSES or not payload['performer']:
        raise ValueError('수행자 이름과 올바른 업무 상태가 필요합니다.')
    if payload['status'] in ('검토 요청','검토 완료'):
        required=('procedure','reason','evidence','result','conclusion')
        if any(not payload[k] for k in required):
            raise ValueError('검토 요청 전 절차·선택 이유·증거·수행 결과·결론을 입력하세요.')
    if payload['status']=='검토 완료':
        if payload['unresolved']:
            raise ValueError('미해결 사항이 남아 있습니다. 보완 후 검토를 완료하세요.')
        if next(s for s in signals(case) if s['id']==signal_id)['flag'] is None:
            raise ValueError('기초 자료가 부족한 사례는 이 시제품에서 검토 완료할 수 없습니다.')
        if not payload['reviewer'] or payload['reviewer']==payload['performer'] or not payload['review_note']:
            raise ValueError('수행자와 다른 검토자 및 검토 의견이 필요합니다.')
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old=read_record(c,case_id,signal_id)
        if data.get('version') != old['version']:
            raise ValueError('다른 창에서 기록이 변경되었습니다. 새로고침 후 다시 입력하세요.')
        if payload['status']=='검토 완료' and old['status'] not in ('검토 요청','검토 완료'):
            raise ValueError('먼저 검토 요청 상태로 저장한 후 검토를 완료하세요.')
        substantive=('requests','procedure','reason','evidence','result','conclusion','performer')
        if payload['status']=='검토 완료' and any(payload[k]!=old[k] for k in substantive):
            raise ValueError('검토 대상 내용이 바뀌었습니다. 검토 요청으로 다시 저장하세요.')
        version=old['version']+1
        encoded=json.dumps(payload,ensure_ascii=False)
        c.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)',(case_id,signal_id,encoded,version))
        c.execute('INSERT INTO history(case_id,signal_id,at,actor,payload) VALUES (?,?,?,?,?)',(case_id,signal_id,datetime.now(timezone.utc).isoformat(),payload['reviewer'] if payload['status']=='검토 완료' else payload['performer'],encoded))
    return {**payload,'version':version}

def export_text(case_id):
    case=next(x for x in all_cases() if x['id']==case_id)
    yr=case['years'][-1]
    fs=case.get('fs_label','별도')
    unit=case.get('unit','백만원')
    data_note='OpenDART 공시 스냅샷 (원문 대조 필요) / 감사판단 및 실제 수행 사실을 증명하는 문서가 아님' if case.get('real') else '가상자료 / 감사판단 및 실제 수행 사실을 증명하는 문서가 아님'
    lines=['계속기업 검토 조서 초안 — 시연용',data_note,f'기업: {case["name"]} | {yr}년 | {fs} | 금액 단위: {unit}','기준 원문: 공식 적용본 대조 전, 연결 보류 (KGA 570 참조 안내 포함)','AI: 미연결, 고정된 절차 예시 사용','']
    labels=dict(zip(FIELDS,('수행자','검토자','요청 자료','선택 절차','선택 이유','증거 참조','실제 수행 결과','작성자 결론','미해결 사항','검토 의견','업무 상태')))
    with connect() as c:
        for s in signals(case):
            r=read_record(c,case_id,s['id'])
            lines += [f'[{s["title"]}] ({s.get("assignee_role","")})',f'발견: {s["value"]}',f'판정: {"자료 부족" if s["flag"] is None else "비정상 · 추가 검토 필요" if s["flag"] else "정상 · 해당 신호 미검출"}',f'근거: {s["source"]}',f'점검 규칙: {s["rule"]}',f'참조 기준: {s.get("standard_ref","")}']
            lines += [f'{labels[k]}: {r[k] or "미입력"}' for k in FIELDS]
            lines += [f'저장 버전: {r["version"]}','']
    return '\n'.join(lines)

class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, mime='application/json; charset=utf-8'):
        raw=body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        url=urlsplit(self.path)
        if url.path=='/':
            return self.send(200,(ROOT/'index.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
        if url.path=='/api/state':
            with connect() as c:
                cases=all_cases(c)
                records={f'{a["id"]}:{r["id"]}':read_record(c,a['id'],r['id']) for a in cases for r in RULES}
                history=[dict(x) for x in c.execute('SELECT id,case_id,signal_id,at,actor,payload FROM history ORDER BY id DESC LIMIT 100')]
            return self.send(200,json.dumps(dict(cases=[{**a,'signals':signals(a)} for a in cases],records=records,history=history),ensure_ascii=False))
        if url.path=='/api/export':
            key=parse_qs(url.query).get('case',[''])[0]
            if key not in {x['id'] for x in all_cases()}: return self.send(404,'{}')
            return self.send(200,export_text(key),'text/plain; charset=utf-8')
        self.send(404,'{}')

    def do_POST(self):
        if self.headers.get('Origin') != f'http://{HOST}:{PORT}':
            return self.send(403,json.dumps({'error':'허용되지 않은 요청 출처입니다.'},ensure_ascii=False))
        if self.path not in ('/api/save','/api/custom-case'): return self.send(404,'{}')
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>250000: raise ValueError('요청 크기가 올바르지 않습니다.')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('잘못된 요청입니다.')
            result=add_custom_case(data) if self.path=='/api/custom-case' else save_record(data)
            self.send(200,json.dumps(result,ensure_ascii=False))
        except (ValueError,TypeError) as e:
            self.send(400,json.dumps({'error':str(e)},ensure_ascii=False))

if __name__=='__main__':
    init_db()
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'GC Audit Assist: http://{HOST}:{PORT}',flush=True)
    if '--no-browser' not in __import__('sys').argv:
        threading.Timer(0.7,lambda:webbrowser.open(f'http://{HOST}:{PORT}')).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
