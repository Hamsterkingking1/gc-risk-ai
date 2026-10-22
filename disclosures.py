"""Replay source-linked borrowing schedules without guessing missing accounts."""
import re
from decimal import Decimal

DEBT_SCOPE = '별도 차입금·사채 장부금액 / 리스부채 제외'


def debt_values(case, year):
    """Return (current, total) in won, or None when the source map is incomplete."""
    y = str(year)
    rec = case.get('debt_reconciliation', {}).get(y)
    source = case.get('report_extracts', {}).get(y, {})
    if not rec or not rec.get('coverage_note') or rec.get('scope') != DEBT_SCOPE:
        return None
    if (source.get('receipt') != case.get('rcept_nos', {}).get(y)
        or source.get('fs_div') != case.get('fs_div')
        or not source.get('filename', '').endswith('_00760.xml')):
        return None
    totals = {'current':0, 'noncurrent':0}
    seen = set()
    for part in rec.get('parts', []):
        bucket = part.get('bucket')
        index = part.get('line_index')
        column = part.get('column')
        unit = part.get('unit')
        sign = part.get('sign', 1)
        if (bucket not in totals or type(index) is not int or type(column) is not int
            or index < 0 or column < 1
            or unit not in ('원','천원','백만원') or type(sign) is not int or sign not in (-1,1)):
            return None
        ident = (index,column)
        if ident in seen:
            return None  # one source cell must never be counted twice
        seen.add(ident)
        try:
            token = source['note_lines'][index].split(' | ')[column].strip()
        except (KeyError, IndexError, TypeError):
            return None
        if token in ('-', '－', '0'):
            value = 0  # dash is zero only in this explicitly mapped disclosure cell
        else:
            token = token.replace(',','').strip('()')
            if not re.fullmatch(r'\d+(?:\.\d+)?', token):
                return None
            value = Decimal(token) * {'원':1,'천원':1000,'백만원':1000000}[unit]
            if value != value.to_integral_value():
                return None
            value = int(value)
        totals[bucket] += sign * value
    if not seen or min(totals.values()) < 0:
        return None
    return totals['current'], sum(totals.values())


def report_wording(source):
    """Only company-specific audit paragraphs, before boilerplate responsibilities."""
    head = source.get('audit_head', [])
    if not head:
        return None
    text = ' '.join(head)
    return '계속기업' in text and ('중요한 불확실성' in text or '의견거절근거' in text)
