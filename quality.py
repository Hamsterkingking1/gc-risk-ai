"""Independent financial checks for gc-risk-ai; no model or audit opinion."""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation, localcontext
from disclosures import debt_values

VERSION = 'gc-risk-quality-2'
DEBT_KEYS = ('st_borrow', 'cur_lt_borrow', 'cur_bonds', 'lt_borrow', 'bonds')


def won(value, unit='원'):
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if s in ('', '-'):
        return None
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,6})?|\((?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,6})?\)', s):
        return None
    if unit not in ('원', '천원', '백만원', '억원'):
        return None
    with localcontext() as ctx:
        ctx.prec = 80
        n = Decimal(('-'+s[1:-1] if s.startswith('(') else s).replace(',', ''))
        # Parenthesized, comma-formatted values need the same normalization.
        if s.startswith('('):
            n = Decimal('-'+s[1:-1].replace(',', ''))
        n *= {'원':1, '천원':1000, '백만원':1000000, '억원':100000000}[unit]
        return int(n) if n.is_finite() and n == n.to_integral_value() else None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def assess(case):
    unit = case.get('unit', '백만원')
    years = case.get('years', [])
    valid_years = (len(years) == 3 and all(type(y) is int for y in years)
                   and years == list(range(years[0], years[0]+3)))
    exact = case.get('amounts_won')
    def values(key):
        v = (exact or case).get(key)
        seq = v if isinstance(v, list) else [v]
        return [won(x, '원' if exact is not None else unit) for x in seq]
    profit, cash = values('profit'), values('cash')
    profit = profit if len(profit) == 3 and valid_years else [None]*3
    cash = cash if len(cash) == 3 and valid_years else [None]*3
    def scalar(k):
        v = values(k)
        return v[0] if len(v) == 1 and valid_years else None
    a, b, due, debt = map(scalar, ('assets', 'liabilities', 'due', 'debt'))
    warnings = list(case.get('source_warnings', []))
    if case.get('real') and not exact:
        warnings.append('기존 백만원 반올림 자료: 원 단위 재수집 전에는 작은 금액·경계값 검증이 제한됩니다.')
    if not valid_years:
        warnings.append('연속된 3개 사업연도를 확인할 수 없습니다.')
    if case.get('custom'):
        warnings.append('사용자 입력 자료: 공시 원문과 단위·연결/별도 기준을 대조해야 합니다.')
    debt_missing = []
    if case.get('real') and case.get('debt_reconciliation'):
        reconciled = debt_values(case, years[-1]) if years else None
        if reconciled:
            due, debt = reconciled
        else:
            due = debt = None
            debt_missing = ['원문 대조표 불완전']
    elif case.get('real'):
        accounts = case.get('accounts_used', {}).get(str(years[-1]) if years else '', {})
        debt_missing = [k for k in DEBT_KEYS if not accounts.get(k)]
        debt_missing += case.get('debt_missing', [])
        if debt_missing:
            due = debt = None
    flags = [
        None if None in profit else all(v < 0 for v in profit),
        None if cash[-1] is None else cash[-1] < 0,
        None if a is None or b is None or a < 0 or b <= 0 else a < b,
        None if due is None or debt is None or not 0 <= due <= debt or debt <= 0 else due*2 >= debt,
        case.get('wording') if type(case.get('wording')) is bool else None,
    ]
    def fmt(x):
        return '자료 없음' if x is None else f'{x:,}원'
    def tri(v):
        return '미확인' if v is None else '해당' if v else '미해당'
    consecutive = None if any(v is None for v in cash[-2:]) else all(v < 0 for v in cash[-2:])
    three = None if None in cash else all(v < 0 for v in cash)
    cash_detail = f'당기 음수: {tri(flags[1])} / 최근 2년 연속 음수: {tri(consecutive)} / 3년 연속 음수: {tri(three)}'
    texts = [
        ' / '.join(f'{y}: {fmt(v)}' for y,v in zip(years, profit)),
        ' / '.join(f'{y}: {fmt(v)}' for y,v in zip(years, cash))+' · '+cash_detail,
        '계산 보류: 유동자산·유동부채 확인 필요' if flags[2] is None else f'{fmt(a)} ÷ {fmt(b)} × 100 = {a/b*100:.2f}%',
        '계산 보류: 차입금 구성계정의 누락·범위 확인 필요' if flags[3] is None else f'{fmt(due)} ÷ {fmt(debt)} × 100 = {due/debt*100:.2f}%',
        '원문 확인 필요' if flags[4] is None else ('전기 별도 감사보고서 기업 고유 문구 ' if case.get('audit_by_year') else '전기 요약 문구 ')+('검출' if flags[4] else '미검출'),
    ]
    if case.get('wording_detail', {}).get('prior_text'):
        texts[4] += ' · '+case['wording_detail']['prior_text']
    if case.get('integrity_errors'):
        warnings.extend(case['integrity_errors'])
        flags[:4] = [None]*4
        texts[:4] = ['판정 보류: 저장 원본과 금액의 일치 여부를 확인하세요.']*4
    return {'flags':flags, 'texts':texts, 'warnings':warnings,
            'debt_missing':sorted(set(debt_missing)), 'cash_detail':cash_detail,
            'cash_coverage':'partial' if None in cash else 'complete',
            'version':VERSION}


def enrich(case, signals):
    q = assess(case)
    for i, s in enumerate(signals):
        s.update(flag=q['flags'][i], value=q['texts'][i], rule_version=VERSION,
                 data_warnings=list(q['warnings']), procedure_status='미검토 제안 · 실제 수행 아님')
        s['provenance'] = {'company':case.get('name'), 'years':case.get('years'),
            'basis':case.get('fs_label'), 'unit':case.get('unit'), 'fetched_at':case.get('fetched_at'),
            'receipt_numbers':case.get('rcept_nos', {}), 'accounts':case.get('accounts_used', {}),
            'source_hashes':case.get('source_hashes', {}),
            'audit_by_year':case.get('audit_by_year', {}),
            'debt_scope':case.get('debt_reconciliation', {}).get(str(case.get('years', [None])[-1]), {}).get('scope'),
            'review_status':'원문 및 회계적 의미 대조 필요'}
        if i == 1:
            s['rule'] = '당기 영업현금흐름 < 0 · 최근 2년/3년 연속 음수는 별도 표시'
            s['coverage'] = q['cash_coverage']
            if q['cash_coverage'] == 'partial':
                s['data_warnings'].append('비교연도 자료 부족: 연속 음수 여부를 확인하세요.')
        if i == 3 and q['debt_missing']:
            s['data_warnings'].append('미확인 차입금 계정: '+', '.join(dict(zip(DEBT_KEYS, ('단기차입금','유동성장기차입금','유동성사채','장기차입금','사채'))).get(k,k) for k in q['debt_missing']))
        if i == 3 and case.get('debt_reconciliation'):
            s['rule'] = '당기 유동 차입금·사채 ÷ 총차입금·사채 ≥ 50% · 리스 제외 장부금액'
            s['data_warnings'].append('주석 표시 단위의 정밀도를 따릅니다. 유동 분류는 계약상 현금 상환일과 다를 수 있습니다.')
        if i == 4 and case.get('audit_by_year'):
            s['rule'] = f"{case['years'][-1]-1}년 별도 감사보고서의 기업 고유 계속기업 사항 · 표준 책임 문구 제외"
        if case.get('custom'):
            s['source'] = '사용자 직접 입력 / '+case['name']+' / 원문 대조 전'
    return signals
