import copy
import unittest
import app
from disclosures import debt_values, report_wording
from quality import assess
from verify_snapshot import verify


class DisclosureTests(unittest.TestCase):
    def company(self,name):
        return copy.deepcopy(next(c for c in app.CASES if c['name']==name))

    def test_all_fifteen_annual_sources_replay(self):
        self.assertEqual(len(app.CASES),5)
        for c in app.CASES:
            self.assertEqual(verify(c),[],c['name'])
            for year in (2023,2024,2025):
                self.assertEqual(len(c['report_extracts'][str(year)]['financial_checks']),4)
                self.assertTrue(all(c['annual_financials'][str(year)][k] is not None for k in ('assets','liabilities','due','debt')))

    def test_samsung_bonds_are_not_counted_twice_and_leases_removed(self):
        c=self.company('삼성전자')
        self.assertEqual(debt_values(c,2025),(15382751000000,38189885000000))
        self.assertEqual(debt_values(c,2024),(33108237000000,33122767000000))

    def test_audit_specific_paragraphs_override_misleading_summary(self):
        samsung=self.company('삼성전자');daegu=self.company('대구백화점');stx=self.company('STX')
        self.assertFalse(report_wording(samsung['report_extracts']['2025']))
        self.assertTrue(daegu['audit_by_year']['2024']['flag'])
        self.assertTrue(stx['audit_by_year']['2025']['flag'])
        self.assertEqual(stx['audit_by_year']['2025']['opinion'],'의견거절')

    def test_duplicate_or_wrong_scope_debt_source_is_rejected(self):
        c=self.company('삼성전자');r=c['debt_reconciliation']['2025']
        r['parts'].append(copy.deepcopy(r['parts'][0]))
        self.assertIsNone(debt_values(c,2025))
        self.assertIsNone(assess(c)['flags'][3])
        c=self.company('삼성전자');c['report_extracts']['2025']['fs_div']='CFS'
        self.assertIsNone(debt_values(c,2025))

    def test_annual_value_and_source_cell_tampering_is_detected(self):
        c=self.company('대구백화점');c['annual_financials']['2023']['assets']='0'
        self.assertTrue(any('연도별 저장 금액' in e for e in verify(c)))
        c=self.company('대구백화점');s=c['report_extracts']['2025'];i=s['financial_checks'][0]['line_index']
        s['note_lines'][i]='변경된 원문'
        self.assertTrue(any('체크섬' in e for e in verify(c)))
        self.assertTrue(any('대조 셀' in e for e in verify(c)))

    def test_stx_rounding_discrepancy_and_disclaimer_remain_visible(self):
        c=self.company('STX')
        self.assertEqual(debt_values(c,2023),(239702000000,240791000000))
        self.assertTrue(any('1백만원 차이' in w for w in assess(c)['warnings']))
        self.assertTrue(any('의견거절' in w for w in assess(c)['warnings']))


if __name__=='__main__':unittest.main()
