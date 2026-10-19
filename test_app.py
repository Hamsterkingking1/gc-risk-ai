import copy
import tempfile
import unittest
from pathlib import Path
import app

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=app.DB
        self.original_cases=app.CASES
        app.DB=Path(self.temp.name)/'test.sqlite3'
        app.CASES=app.SYNTHETIC_CASES+app.original_cases if hasattr(app,'original_cases') else app.SYNTHETIC_CASES+self.original_cases
        app.init_db()
    def tearDown(self):
        app.DB=self.original
        app.CASES=self.original_cases
        self.temp.cleanup()
    def payload(self,case='risk'):
        with app.connect() as c:
            r=app.read_record(c,case,'cash')
        return {**r,'case_id':case,'signal_id':'cash','performer':'A','reason':'가상 사유','evidence':'가상 증거 E1','result':'가상 대사 수행','conclusion':'추가 확인 필요'}
    def test_three_cases(self):
        self.assertTrue(all(c.get('real') for c in self.original_cases))
        self.assertEqual([s['flag'] for s in app.signals(app.SYNTHETIC_CASES[0])],[True]*5)
        self.assertEqual([s['flag'] for s in app.signals(app.SYNTHETIC_CASES[1])],[False]*5)
        self.assertEqual([s['flag'] for s in app.signals(app.SYNTHETIC_CASES[2])],[None]*5)
    def test_zero_denominator_and_boundaries(self):
        c=copy.deepcopy(app.CASES[0]);c['liabilities']=0;c['debt']=0
        self.assertIsNone(app.signals(c)[2]['flag']);self.assertIsNone(app.signals(c)[3]['flag'])
        c['liabilities']=650;c['debt']=1000;c['due']=500
        self.assertFalse(app.signals(c)[2]['flag']);self.assertTrue(app.signals(c)[3]['flag'])
        c['profit']=[-1,0,-1];self.assertFalse(app.signals(c)[0]['flag'])
    def test_missing_is_not_zero(self):
        c=copy.deepcopy(app.CASES[0]);c['cash'][1]=None
        self.assertIsNone(app.signals(c)[1]['flag'])
    def test_save_history_and_reload(self):
        r=app.save_record(self.payload())
        with app.connect() as c:
            self.assertEqual(app.read_record(c,'risk','cash')['evidence'],'가상 증거 E1')
            self.assertEqual(c.execute('SELECT count(*) FROM history').fetchone()[0],1)
        self.assertEqual(r['version'],1)
    def test_version_conflict(self):
        p=self.payload();app.save_record(p)
        with self.assertRaisesRegex(ValueError,'다른 창'): app.save_record(p)
    def test_request_needs_evidence(self):
        p=self.payload();p.update(status='검토 요청',evidence='')
        with self.assertRaises(ValueError):app.save_record(p)
    def test_complete_requires_request(self):
        p=self.payload();p.update(status='검토 완료',reviewer='B',review_note='확인')
        with self.assertRaisesRegex(ValueError,'먼저 검토 요청'):app.save_record(p)
    def test_review_and_reopen(self):
        p=self.payload();p['status']='검토 요청';p.update(app.save_record(p))
        p.update(status='검토 완료',reviewer='B',review_note='가상 검토 완료');p.update(app.save_record(p))
        self.assertEqual(p['status'],'검토 완료')
        p['result']='수정된 결과'
        with self.assertRaisesRegex(ValueError,'내용이 바뀌었습니다'):app.save_record(p)
        p['status']='수행 중';app.save_record(p)
    def test_same_reviewer_blocked(self):
        p=self.payload();p.update(status='검토 완료',reviewer='A',review_note='확인')
        with self.assertRaises(ValueError):app.save_record(p)
    def test_unresolved_blocked(self):
        p=self.payload();p.update(status='검토 완료',reviewer='B',review_note='확인',unresolved='추가 계약 필요')
        with self.assertRaisesRegex(ValueError,'미해결'):app.save_record(p)
    def test_missing_case_blocked(self):
        p=self.payload('missing');p.update(status='검토 완료',reviewer='B',review_note='확인')
        with self.assertRaisesRegex(ValueError,'기초 자료'):app.save_record(p)
    def test_export_no_fabricated_result(self):
        text=app.export_text('risk')
        self.assertIn('실제 수행 결과: 미입력',text)
        self.assertIn('공식 적용본 대조 전',text)
        app.save_record(self.payload())
        self.assertIn('실제 수행 결과: 가상 대사 수행',app.export_text('risk'))
    def test_dart_parse_and_real_case_load(self):
        import dart_fetch, json
        self.assertEqual(dart_fetch.to_number('1,234,567'), 1234567)
        self.assertEqual(dart_fetch.to_number('(50,000)'), -50000)
        self.assertIsNone(dart_fetch.to_number('-'))
        rows=[{'sj_div':'IS','account_id':'ifrs-full_ProfitLoss','account_nm':'당기순손실','thstrm_amount':'-12,000,000,000'}]
        self.assertEqual(dart_fetch.pick(rows,'profit'),(-12000000000,'당기순손실'))
        cdir=Path(self.temp.name)/'cases'; cdir.mkdir()
        snap={'id':'real_000000_2025_OFS','name':'테스트상장사','real':True,'fs_label':'별도','unit':'백만원','years':[2023,2024,2025],'profit':[-10,-20,-30],'cash':[-5,-6,-7],'assets':400,'liabilities':500,'debt':300,'due':200,'wording':True,'wording_detail':{'prior_year':2024,'prior_text':'계속기업 관련 중요한 불확실성'},'sources':['S1','S2','S3','S4','S5']}
        (cdir/'real_000000_2025_OFS.json').write_text(json.dumps(snap,ensure_ascii=False),encoding='utf-8')
        loaded=app.load_real_cases(cdir)
        self.assertEqual(len(loaded),1)
        sigs=app.signals(loaded[0])
        self.assertEqual([s['flag'] for s in sigs],[True]*5)
        self.assertIn('계속기업 관련 중요한 불확실성',sigs[4]['value'])
        self.assertTrue(all(s.get('team_tasks') and s.get('procedure_templates') for s in sigs))
        custom=app.add_custom_case({'name':'직접입력기업','fs_label':'연결','profit_2023':'-10','profit_2024':'-20','profit_2025':'-30','cash_2023':'10','cash_2024':'20','cash_2025':'30','assets':'900','liabilities':'1000','due':'600','debt':'1000','wording':'true'})
        self.assertEqual([s['flag'] for s in custom['signals']],[True,False,True,True,True])

if __name__=='__main__': unittest.main()
