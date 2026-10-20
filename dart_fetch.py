"""OpenDART에서 실제 기업의 3개년 재무 수치와 감사의견 문구를 받아 시연용 스냅샷 JSON을 만듭니다.

사용법 (Python 표준 라이브러리만 사용):
    python dart_fetch.py --stock 123456 --year 2025            # 별도(OFS) 기준
    python dart_fetch.py --stock 123456 --year 2025 --fs CFS   # 연결 기준
    python dart_fetch.py --find 회사명                          # 고유번호·종목코드 검색

인증키는 코드에 적지 않습니다. 환경변수 DART_API_KEY 또는 저장소 루트의 .env 파일
(DART_API_KEY=...)에서 읽습니다. .env는 .gitignore에 포함되어 있습니다.

결과는 cases/real_<종목코드>_<연도>_<OFS|CFS>.json 으로 저장되며 app.py가 자동으로 불러옵니다.
스냅샷에는 공개 공시 수치와 접수번호만 들어가고 인증키는 들어가지 않습니다.
"""
from quality import won, digest, DEBT_KEYS
import argparse
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'data' / 'dart_cache'
OUT = ROOT / 'cases'
API = 'https://opendart.fss.or.kr/api/'
VIEW = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='
ANNUAL = '11011'  # 사업보고서

# 표준 계정 ID(XBRL) 우선, 없으면 계정명으로 찾습니다. 회사마다 계정 체계가 달라 누락될 수 있습니다.
ACCOUNTS = {
    'profit': (('IS', 'CIS'), ('ifrs-full_ProfitLoss',), ('당기순이익', '당기순손실', '당기순이익(손실)', '당기순손익')),
    'cash': (('CF',), ('ifrs-full_CashFlowsFromUsedInOperatingActivities',), ('영업활동현금흐름', '영업활동으로인한현금흐름', '영업활동으로 인한 현금흐름')),
    'assets': (('BS',), ('ifrs-full_CurrentAssets',), ('유동자산',)),
    'liabilities': (('BS',), ('ifrs-full_CurrentLiabilities',), ('유동부채',)),
    'st_borrow': (('BS',), ('ifrs-full_ShorttermBorrowings', 'dart_ShortTermBorrowings'), ('단기차입금',)),
    'cur_lt_borrow': (('BS',), ('ifrs-full_CurrentPortionOfLongtermBorrowings', 'dart_CurrentPortionOfLongTermBorrowings'), ('유동성장기차입금', '유동성장기부채')),
    'cur_bonds': (('BS',), ('dart_CurrentPortionOfBonds',), ('유동성사채', '유동성전환사채', '전환사채(유동)')),
    'lt_borrow': (('BS',), ('ifrs-full_LongtermBorrowings', 'dart_LongTermBorrowingsGross'), ('장기차입금',)),
    'bonds': (('BS',), ('dart_BondsIssued', 'ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued'), ('사채', '전환사채')),
}
GC_WORDS = ('계속기업', '존속능력', '중요한 불확실성')


def api_key():
    key = os.environ.get('DART_API_KEY', '').strip()
    env = ROOT / '.env'
    if not key and env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('DART_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"\'')
    if len(key) != 40:
        sys.exit('DART 인증키가 없습니다. 저장소 루트에 .env 파일을 만들고 DART_API_KEY=발급받은40자리키 를 적어주세요.')
    return key


def get(path, **params):
    params['crtfc_key'] = api_key()
    url = API + path + '?' + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1.5)


def get_json(path, **params):
    data = json.loads(get(path, **params).decode('utf-8'))
    status = data.get('status')
    if status == '013':  # 조회된 데이터 없음
        return []
    if status != '000':
        raise RuntimeError(f'OpenDART 오류 {status}: {data.get("message")}')
    return data.get('list', [])


def corp_list():
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / 'corp_codes.json'
    if path.exists() and time.time() - path.stat().st_mtime < 7 * 86400:
        return json.loads(path.read_text(encoding='utf-8'))
    raw = get('corpCode.xml')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])
    rows = [{k: (e.findtext(k) or '').strip() for k in ('corp_code', 'corp_name', 'stock_code')} for e in ET.fromstring(xml).iter('list')]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    return rows


def to_number(text):
    return won(text)


def pick(rows, key):
    """계정 하나를 찾아 (원 단위 금액, 사용한 계정명)을 돌려줍니다. 못 찾으면 (None, None)."""
    divs, ids, names = ACCOUNTS[key]
    pool = [r for r in rows if r.get('sj_div') in divs]
    matches = [r for r in pool if r.get('account_id') in ids]
    if not matches:
        norm = lambda v: (v or '').replace(' ', '')
        matches = [r for r in pool if norm(r.get('account_nm')) in {norm(n) for n in names}]
    if not matches:
        return None, None
    values = [to_number(r.get('thstrm_amount')) for r in matches]
    # Missing or conflicting candidate rows are not silently resolved by order.
    if None in values or len(set(values)) != 1:
        return None, None
    return values[0], matches[0].get('account_nm')


def financials(corp_code, year, fs):
    rows = get_json('fnlttSinglAcntAll.json', corp_code=corp_code, bsns_year=str(year), reprt_code=ANNUAL, fs_div=fs)
    if not rows:
        return None
    out = {'rcept_no': rows[0].get('rcept_no'), 'accounts': {}, 'raw_rows':rows, 'sha256':digest(rows)}
    if any(r.get('corp_code', corp_code) != corp_code
           or str(r.get('bsns_year', year)) != str(year)
           or r.get('fs_div', fs) != fs for r in rows):
        raise ValueError('DART 응답 기업·연도·연결/별도 불일치')
    if len({r.get('rcept_no') for r in rows}) != 1:
        raise ValueError('서로 다른 접수번호가 섞인 DART 응답')
    for key in ACCOUNTS:
        value, name = pick(rows, key)
        out['accounts'][key] = {'won': value, 'account_nm': name}
    return out


def auditor_opinion(corp_code, year):
    rows = get_json('accnutAdtorNmNdAdtOpinion.json', corp_code=corp_code, bsns_year=str(year), reprt_code=ANNUAL)
    # 당기(bsns_year와 같은 사업연도) 행을 우선 사용합니다.
    rows = sorted(rows, key=lambda r: 0 if str(year) in (r.get('bsns_year') or '') else 1)
    return rows[0] if rows else None


def mil(won):
    return None if won is None else str(__import__('decimal').Decimal(won) / 1_000_000)


def build(stock, year, fs):
    corp = next((c for c in corp_list() if c['stock_code'] == stock), None)
    if corp is None:
        sys.exit(f'종목코드 {stock}에 해당하는 상장사를 찾지 못했습니다.')
    years = [year - 2, year - 1, year]
    fin = {}
    for y in years:
        fin[y] = financials(corp['corp_code'], y, fs)
        time.sleep(0.3)
    cur = fin[year]
    if cur is None:
        sys.exit(f'{year}년 사업보고서 재무제표({fs})가 OpenDART에 없습니다. 연도나 --fs 를 바꿔 보세요.')
    acc = lambda y, k: (fin[y] or {}).get('accounts', {}).get(k, {}).get('won')

    # 차입금 만기 부담: (단기차입금 + 유동성장기차입금 + 유동성사채) ÷ (위 합계 + 장기차입금 + 사채)
    due_parts = [acc(year, k) for k in ('st_borrow', 'cur_lt_borrow', 'cur_bonds')]
    long_parts = [acc(year, k) for k in ('lt_borrow', 'bonds')]
    due = sum(v for v in due_parts if v is not None) if any(v is not None for v in due_parts) else None
    debt_missing = [k for k in DEBT_KEYS if acc(year, k) is None]
    debt = None if debt_missing else sum(due_parts + long_parts)
    if debt_missing:
        due = None

    op_cur = auditor_opinion(corp['corp_code'], year)
    op_prev = auditor_opinion(corp['corp_code'], year - 1)

    def gc_text(op):
        if not op:
            return None, ''
        hits = [f'{k}: {v}' for k, v in op.items() if isinstance(v, str) and any(w in v for w in GC_WORDS)]
        return bool(hits), ' / '.join(hits)[:600]

    prev_flag, prev_text = gc_text(op_prev)
    cur_flag, cur_text = gc_text(op_cur)
    unit = '백만원'
    label = '별도' if fs == 'OFS' else '연결'
    rc = {y: (fin[y] or {}).get('rcept_no') for y in years}
    src_years = ', '.join(f'{y} 사업보고서 {rc[y]}' for y in years if rc[y])
    case = {
        'id': f'real_{stock}_{year}_{fs}',
        'name': corp['corp_name'],
        'real': True,
        'stock_code': stock,
        'corp_code': corp['corp_code'],
        'fs_div': fs,
        'fs_label': label,
        'unit': unit,
        'schema_version':'gc-case-2',
        'amounts_won': {
            'profit':[None if acc(y,'profit') is None else str(acc(y,'profit')) for y in years],
            'cash':[None if acc(y,'cash') is None else str(acc(y,'cash')) for y in years],
            'assets':None if acc(year,'assets') is None else str(acc(year,'assets')),
            'liabilities':None if acc(year,'liabilities') is None else str(acc(year,'liabilities')),
            'debt':None if debt is None else str(debt), 'due':None if due is None else str(due)},
        'debt_missing':debt_missing,
        'source_hashes':{str(y):fin[y]['sha256'] for y in years if fin[y]},
        'raw_financials':{str(y):fin[y]['raw_rows'] for y in years if fin[y]},
        'years': years,
        'profit': [mil(acc(y, 'profit')) for y in years],
        'cash': [mil(acc(y, 'cash')) for y in years],
        'assets': mil(acc(year, 'assets')),
        'liabilities': mil(acc(year, 'liabilities')),
        'debt': mil(debt),
        'due': mil(due),
        # 문구 신호: 전기 감사보고서 기준(기존 규칙 유지). 당기 문구는 참고로 함께 저장합니다.
        'wording': prev_flag,
        'wording_detail': {'prior_year': year - 1, 'prior_text': prev_text, 'current_flag': cur_flag, 'current_text': cur_text,
                           'current_opinion': (op_cur or {}).get('adt_opinion'), 'auditor': (op_cur or {}).get('adtor')},
        'rcept_nos': rc,
        'accounts_used': {y: {k: v.get('account_nm') for k, v in (fin[y] or {}).get('accounts', {}).items()} for y in years},
        'sources': [
            f'OpenDART 재무제표({label}) / {src_years}',
            f'OpenDART 재무제표({label}) / {src_years}',
            f'OpenDART 재무상태표({label}) / {year} 사업보고서 {rc[year]}',
            f'OpenDART 재무상태표({label}) 차입금·사채 계정 합산 / {year} 사업보고서 {rc[year]}',
            f'OpenDART 회계감사인의 명칭 및 감사의견 / {year - 1} 사업보고서 (당기 참고: {"관련 문구 있음" if cur_flag else "관련 문구 없음" if cur_flag is False else "미확인"})',
        ],
        'links': {str(y): VIEW + rc[y] for y in years if rc[y]},
        'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / f'{case["id"]}.json'
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
    return path, case


def main():
    p = argparse.ArgumentParser(description='OpenDART 실제 기업 스냅샷 생성')
    p.add_argument('--stock', help='6자리 종목코드')
    p.add_argument('--year', type=int, default=2025, help='당기 사업연도 (기본 2025)')
    p.add_argument('--fs', choices=('OFS', 'CFS'), default='OFS', help='OFS=별도, CFS=연결')
    p.add_argument('--find', help='회사명 일부로 검색')
    a = p.parse_args()
    if a.find:
        for c in corp_list():
            if a.find in c['corp_name'] and c['stock_code']:
                print(c['stock_code'], c['corp_code'], c['corp_name'])
        return
    if not a.stock:
        p.error('--stock 또는 --find 가 필요합니다.')
    path, case = build(a.stock, a.year, a.fs)
    print(f'저장: {path}')
    for k in ('profit', 'cash'):
        print(k, dict(zip(case['years'], case[k])))
    print('유동자산/유동부채', case['assets'], case['liabilities'], '| 만기 1년 이내/총차입', case['due'], case['debt'])
    print('전기 계속기업 문구:', case['wording'], '| 당기:', case['wording_detail']['current_flag'])
    missing = [f'{y}:{k}' for y, m in case['accounts_used'].items() for k, v in m.items() if v is None]
    if missing:
        print('찾지 못한 계정(원문 확인 필요):', ', '.join(missing))


if __name__ == '__main__':
    main()

