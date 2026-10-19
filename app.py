"""Local, synthetic-data audit workflow prototype. Python standard library only."""
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
CASES = [
    dict(id='risk', name='가상 A제조', years=[2023,2024,2025], profit=[-100,-80,-120], cash=[-60,-90,-110], assets=650, liabilities=1000, debt=800, due=500, wording=True),
    dict(id='clear', name='가상 B제조', years=[2023,2024,2025], profit=[100,130,160], cash=[80,110,140], assets=1800, liabilities=1000, debt=800, due=200, wording=False),
    dict(id='missing', name='가상 C제조', years=[2023,2024,2025], profit=[-100,None,-50], cash=[-60,None,-110], assets=650, liabilities=None, debt=None, due=300, wording=None),
]
RULES = [
    dict(id='loss', title='반복 손실', rule='최근 3개년 당기순손익이 모두 음수', why='손실의 지속 원인과 경영진의 대응 계획을 확인합니다.', requests='경영진 계속기업 평가, 손익 개선계획, 최근 실적', procedure='손실의 주요 원인을 구분하고 개선계획의 가정을 최근 실적과 비교합니다.'),
    dict(id='cash', title='영업현금흐름 악화', rule='최근 3개년 영업현금흐름이 모두 음수', why='영업에서 필요한 현금을 마련할 수 있는지 검토합니다.', requests='월별 자금계획, 현금 잔액 자료, 매출·회수 실적', procedure='자금계획 시작 잔액을 대사하고 매출·회수 가정과 실제 실적의 차이를 확인합니다.'),
    dict(id='liquidity', title='유동성 저하', rule='당기 유동비율 < 100% (유동자산 ÷ 유동부채 × 100)', why='단기 지급 의무에 대응할 재원과 회수 가능성을 확인합니다.', requests='유동자산 명세, 지급 일정, 자금계획', procedure='유동자산의 회수 예상 시점과 지급 일정을 비교하고 부족 자금의 조달 근거를 확인합니다.'),
    dict(id='debt', title='차입금 상환 부담', rule='1년 이내 만기도래 차입금 ÷ 총차입금 ≥ 50%', why='차입금 만기 집중과 상환·연장 계획의 실행 가능성을 확인합니다.', requests='차입금 만기표, 대출 계약, 연장 협의 자료', procedure='만기표를 계약과 대사하고 상환 재원 및 연장 계획의 뒷받침 자료를 확인합니다.'),
    dict(id='wording', title='계속기업 관련 문구', rule='전기 보고서 관련 문구 존재 여부 (가상자료의 사전 입력값)', why='전기 문구와 관련된 당기 상황 및 개선 여부를 다시 확인합니다.', requests='전기 감사보고서, 당기 경영진 평가, 당기 주석 초안', procedure='전기 문구의 대상 상황과 당기 변화를 비교합니다. 전기 결론을 당기 결론으로 전용하지 않습니다.'),
]
FIELDS = ('performer','reviewer','requests','procedure','reason','evidence','result','conclusion','unresolved','review_note','status')
STATUSES = ('미착수','자료 요청','수행 중','검토 요청','검토 완료')

def signals(case):
    values = []
    for key in ('profit','cash'):
        xs = case[key]
        values.append((None if any(x is None for x in xs) else all(x < 0 for x in xs), ' / '.join(f'{year}: ' + ('자료 없음' if x is None else f'{x:,}') for year,x in zip(case['years'],xs)) + ' (백만원)'))
    a,b = case['assets'],case['liabilities']
    ratio = a/b*100 if a is not None and b is not None and b > 0 else None
    values.append((None if ratio is None else ratio < 100, '계산 보류' if ratio is None else f'{a:,} ÷ {b:,} × 100 = {ratio:.1f}%'))
    a,b = case['due'],case['debt']
    ratio = a/b*100 if a is not None and b is not None and b > 0 and 0 <= a <= b else None
    values.append((None if ratio is None else ratio >= 50, '계산 보류' if ratio is None else f'{a:,} ÷ {b:,} × 100 = {ratio:.1f}%'))
    values.append((case['wording'], '원문 미확보' if case['wording'] is None else '가상 전기 보고서: ' + ('관련 문구 있음' if case['wording'] else '관련 문구 없음')))
    return [{**r, 'flag':v[0], 'value':v[1], 'source':f'가상 데이터 / {case["name"]} / ' + ('2023~2025년 손익·현금흐름표' if i<2 else '2025년 재무상태·차입금 명세' if i<4 else '2024년 보고서 메타데이터'), 'standard_status':'공식 적용본 대조 전 · 기준 연결 보류'} for i,(r,v) in enumerate(zip(RULES,values))]

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

def read_record(c, case_id, signal_id):
    row=c.execute('SELECT payload,version FROM records WHERE case_id=? AND signal_id=?',(case_id,signal_id)).fetchone()
    if row:
        return {**json.loads(row['payload']), 'version':row['version']}
    rule=next(r for r in RULES if r['id']==signal_id)
    return {**dict.fromkeys(FIELDS,''), 'requests':rule['requests'],'procedure':rule['procedure'],'status':'미착수','version':0}

def save_record(data):
    case_id, signal_id = data.get('case_id'), data.get('signal_id')
    case=next((x for x in CASES if x['id']==case_id),None)
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
    case=next(x for x in CASES if x['id']==case_id)
    lines=['계속기업 검토 조서 초안 — 시연용','가상자료 / 감사판단 및 실제 수행 사실을 증명하는 문서가 아님',f'기업: {case["name"]} | 2025년 | 별도 | 금액 단위: 백만원','기준 원문: 공식 적용본 대조 전, 연결 보류','AI: 미연결, 고정된 절차 예시 사용','']
    labels=dict(zip(FIELDS,('수행자','검토자','요청 자료','선택 절차','선택 이유','증거 참조','실제 수행 결과','작성자 결론','미해결 사항','검토 의견','업무 상태')))
    with connect() as c:
        for s in signals(case):
            r=read_record(c,case_id,s['id'])
            lines += [f'[{s["title"]}]',f'발견: {s["value"]}',f'판정: {"자료 부족" if s["flag"] is None else "추가 검토 필요" if s["flag"] else "해당 신호 미검출"}',f'근거: {s["source"]}',f'점검 규칙: {s["rule"]}']
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
                records={f'{a["id"]}:{r["id"]}':read_record(c,a['id'],r['id']) for a in CASES for r in RULES}
                history=[dict(x) for x in c.execute('SELECT id,case_id,signal_id,at,actor,payload FROM history ORDER BY id DESC LIMIT 100')]
            return self.send(200,json.dumps(dict(cases=[{**a,'signals':signals(a)} for a in CASES],records=records,history=history),ensure_ascii=False))
        if url.path=='/api/export':
            key=parse_qs(url.query).get('case',[''])[0]
            if key not in {x['id'] for x in CASES}: return self.send(404,'{}')
            return self.send(200,export_text(key),'text/plain; charset=utf-8')
        self.send(404,'{}')

    def do_POST(self):
        if self.headers.get('Origin') != f'http://{HOST}:{PORT}':
            return self.send(403,json.dumps({'error':'허용되지 않은 요청 출처입니다.'},ensure_ascii=False))
        if self.path!='/api/save': return self.send(404,'{}')
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>250000: raise ValueError('요청 크기가 올바르지 않습니다.')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('잘못된 요청입니다.')
            result=save_record(data)
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
