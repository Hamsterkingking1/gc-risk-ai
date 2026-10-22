"""Recheck saved DART rows, exact amounts and scope without network calls.

Hashes detect accidental changes, not source authenticity or accounting validity.
"""
import json
import sys
from pathlib import Path
from quality import digest, DEBT_KEYS, won
from dart_fetch import pick
from disclosures import debt_values, report_wording


def verify(case):
    if case.get('schema_version') not in ('gc-case-2', 'gc-case-3'):
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
    if case.get('schema_version') == 'gc-case-3':
        for year in years:
            y=str(year)
            source=case.get('report_extracts', {}).get(y, {})
            if digest(source) != case.get('report_extract_hashes', {}).get(y):
                errors.append(f'{year}: 감사보고서 발췌 체크섬 불일치')
            if (source.get('receipt') != case.get('rcept_nos', {}).get(y)
                or source.get('fs_div') != case.get('fs_div')):
                errors.append(f'{year}: 감사보고서 원문 범위 불일치')
            for check in source.get('financial_checks', []):
                try:
                    token=source['note_lines'][check['line_index']].split(' | ')[check['column']].strip()
                    value=0 if token in ('-','－') else won(token,check['unit'])
                    if value != extracted[year].get(check['key']):
                        errors.append(f'{year}: 재무제표 본문과 API 수치 불일치')
                except (KeyError,IndexError,TypeError):
                    errors.append(f'{year}: 재무제표 대조 셀 누락')
            if {v.get('key') for v in source.get('financial_checks', [])} != {'profit','cash','assets','liabilities'}:
                errors.append(f'{year}: 재무제표 본문 대조 항목 누락')
            debt_pair=debt_values(case,year)
            if debt_pair is None:
                errors.append(f'{year}: 차입금 원문 대조표 불완전')
                continue
            d,t=debt_pair
            annual={k:str(extracted[year].get(k)) for k in ('profit','cash','assets','liabilities')}
            annual.update(due=str(d),debt=str(t))
            if annual != case.get('annual_financials', {}).get(y):
                errors.append(f'{year}: 연도별 저장 금액 재계산 불일치')
            if report_wording(source) != case.get('audit_by_year', {}).get(y, {}).get('flag'):
                errors.append(f'{year}: 감사보고서 문구 판정 불일치')
        pair=debt_values(case,years[-1])
        due,total=pair if pair else (None,None)
        if case.get('wording') != case.get('audit_by_year', {}).get(str(years[-1]-1), {}).get('flag'):
            errors.append('전기 감사보고서 판정 연도 불일치')
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
