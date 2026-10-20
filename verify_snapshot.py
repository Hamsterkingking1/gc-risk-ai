"""Recheck saved DART rows, exact amounts and scope without network calls.

Hashes detect accidental changes, not source authenticity or accounting validity.
"""
import json
import sys
from pathlib import Path
from quality import digest, DEBT_KEYS
from dart_fetch import pick


def verify(case):
    if case.get('schema_version') != 'gc-case-2':
        return ['기존 자료: 원 단위 원본 응답 재수집 필요']
    errors = []
    years = case.get('years', [])
    rows_by_year = case.get('raw_financials', {})
    extracted = {}
    for year in years:
        rows = rows_by_year.get(str(year))
        if rows is None:
            extracted[year] = {}
            continue
        if digest(rows) != case.get('source_hashes', {}).get(str(year)):
            errors.append(f'{year}: 원본 응답 체크섬 불일치')
        for row in rows:
            if (row.get('corp_code') != case.get('corp_code')
                or str(row.get('bsns_year')) != str(year)
                or row.get('fs_div', case.get('fs_div')) != case.get('fs_div')
                or row.get('currency', 'KRW') != 'KRW'
                or row.get('rcept_no') != case.get('rcept_nos', {}).get(str(year))):
                errors.append(f'{year}: 원본 기업·연도·통화·기준·접수번호 불일치')
                break
        extracted[year] = {k:pick(rows,k)[0] for k in ('profit','cash','assets','liabilities',*DEBT_KEYS)}
    if not years:
        return errors+['연도 누락']
    last = extracted.get(years[-1], {})
    parts = [last.get(k) for k in DEBT_KEYS]
    total = None if None in parts else sum(parts)
    due = None if None in parts else sum(parts[:3])
    expected = {
        'profit':[extracted[y].get('profit') for y in years],
        'cash':[extracted[y].get('cash') for y in years],
        'assets':last.get('assets'), 'liabilities':last.get('liabilities'),
        'due':due,'debt':total}
    def stringify(v):
        return [stringify(x) for x in v] if isinstance(v,list) else None if v is None else str(v)
    if {k:stringify(v) for k,v in expected.items()} != case.get('amounts_won'):
        errors.append('원본 응답 재계산과 저장 금액 불일치')
    return sorted(set(errors))


if __name__ == '__main__':
    errors=verify(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    print('\n'.join(errors) if errors else '저장된 응답·금액 재대조 통과 (회계적 적정성 검증은 별도)')
    sys.exit(bool(errors))
