import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import dart_fetch
from quality import assess, won, DEBT_KEYS, digest
from verify_snapshot import verify


class QualityTests(unittest.TestCase):
    def case(self):
        return copy.deepcopy(app.SYNTHETIC_CASES[0])

    def test_one_won_loss_survives(self):
        c=self.case(); c['cash']=['1','2','-0.000001']
        self.assertTrue(assess(c)['flags'][1])
        self.assertIn('-1원',assess(c)['texts'][1])

    def test_large_integer_precision(self):
        self.assertEqual(won('9007199254740993'),9007199254740993)
        self.assertEqual(dart_fetch.to_number('9007199254740993'),9007199254740993)

    def test_invalid_amounts(self):
        for v in ['NaN','Infinity','1e9','1,2','0.0000001',True]:
            self.assertIsNone(won(v))
        self.assertEqual(won('(1,234)'),-1234)

    def test_current_cash_and_trend_are_separate(self):
        c=self.case();c['cash']=[10,20,-1]
        q=assess(c)
        self.assertTrue(q['flags'][1])
        self.assertIn('3년 연속 음수: 미해당',q['cash_detail'])

    def test_missing_comparison_keeps_current_signal(self):
        c=self.case();c['cash']=[None,20,-1]
        self.assertTrue(assess(c)['flags'][1])
        self.assertEqual(assess(c)['cash_coverage'],'partial')
        c['cash']=[10,20,None]
        self.assertIsNone(assess(c)['flags'][1])

    def test_negative_balance_deferred(self):
        c=self.case();c['assets']=-1
        self.assertIsNone(assess(c)['flags'][2])

    def test_wrong_year_scope(self):
        c=self.case();c['years']=[2023,2025,2024]
        self.assertEqual(assess(c)['flags'][:4],[None]*4)

    def test_partial_debt_not_zero(self):
        c=self.case();c.update(real=True,accounts_used={'2025':{'st_borrow':'단기차입금'}})
        self.assertIsNone(assess(c)['flags'][3])
        c['accounts_used']['2025']={k:k for k in DEBT_KEYS}
        self.assertTrue(assess(c)['flags'][3])

    def test_conflicting_account_candidates(self):
        row={'sj_div':'BS','account_id':'ifrs-full_CurrentAssets','account_nm':'유동자산','thstrm_amount':'100'}
        self.assertEqual(dart_fetch.pick([row,{**row,'thstrm_amount':'101'}],'assets'),(None,None))
        self.assertEqual(dart_fetch.pick([row,row],'assets'),(100,'유동자산'))

    def snapshot(self):
        def fin(corp,year,fs):
            rows=[]
            for k,(divs,ids,names) in dart_fetch.ACCOUNTS.items():
                rows.append({'corp_code':corp,'bsns_year':str(year),'fs_div':fs,'currency':'KRW',
                    'rcept_no':str(year)+'001','sj_div':divs[0],'account_id':ids[0],
                    'account_nm':names[0],'thstrm_amount':'-1' if k in ('profit','cash') else '100'})
            return {'rcept_no':str(year)+'001','raw_rows':rows,'sha256':digest(rows),
                    'accounts':{k:{'won':dart_fetch.pick(rows,k)[0],'account_nm':dart_fetch.pick(rows,k)[1]} for k in dart_fetch.ACCOUNTS}}
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch.object(dart_fetch,'OUT',Path(d)), \
             patch.object(dart_fetch,'corp_list',return_value=[{'stock_code':'000000','corp_code':'corp','corp_name':'검증기업'}]), \
             patch.object(dart_fetch,'financials',side_effect=fin), \
             patch.object(dart_fetch,'auditor_opinion',return_value=None),patch.object(dart_fetch.time,'sleep'):
            _,c=dart_fetch.build('000000',2025,'OFS')
            return json.loads(json.dumps(c))

    def test_snapshot_replay_and_tamper(self):
        c=self.snapshot()
        self.assertEqual(verify(c),[])
        self.assertEqual(c['amounts_won']['cash'],['-1']*3)
        c['amounts_won']['cash'][2]='0'
        self.assertIn('원본 응답 재계산과 저장 금액 불일치',verify(c))

    def test_source_scope_and_hash_tamper(self):
        c=self.snapshot();c['raw_financials']['2025'][0]['corp_code']='other'
        errors=verify(c)
        self.assertTrue(any('체크섬' in e for e in errors))
        self.assertTrue(any('기업' in e for e in errors))

    def test_snapshot_errors_block_flags(self):
        c=self.case();c['integrity_errors']=['변조 확인 필요']
        self.assertEqual(assess(c)['flags'][:4],[None]*4)

    def test_python_browser_flag_parity(self):
        node=shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
        cases=[self.case(),self.snapshot()]
        for cash in ([1,2,-1],[None,2,-1],[1,2,None],['0','0','-0.000001']):
            c=self.case();c['cash']=cash;cases.append(c)
        for k,v in [('assets',-1),('liabilities',0),('due',9999),('debt',0)]:
            c=self.case();c[k]=v;cases.append(c)
        cases+=json.loads((Path(__file__).parent/'site/dist/cases.json').read_text(encoding='utf-8'))
        js="const q=require('./site/dist/quality.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c=>q.enrich(c,[{},{},{},{},{}]).map(s=>s.flag)))));"
        result=subprocess.run([node,'-e',js],input=json.dumps(cases),text=True,capture_output=True,cwd=Path(__file__).parent,check=True)
        self.assertEqual(json.loads(result.stdout),[assess(c)['flags'] for c in cases])


if __name__=='__main__':
    unittest.main()
