import copy
import tempfile
import unittest
from pathlib import Path
import app

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=app.DB
        app.DB=Path(self.temp.name)/'test.sqlite3'
        app.init_db()
    def tearDown(self):
        app.DB=self.original
        self.temp.cleanup()
    def payload(self,case='risk'):
        with app.connect() as c:
            r=app.read_record(c,case,'cash')
        return {**r,'case_id':case,'signal_id':'cash','performer':'A','reason':'가상 사유','evidence':'가상 증거 E1','result':'가상 대사 수행','conclusion':'추가 확인 필요'}
    def test_three_cases(self):
        self.assertEqual([s['flag'] for s in app.signals(app.CASES[0])],[True]*5)
        self.assertEqual([s['flag'] for s in app.signals(app.CASES[1])],[False]*5)
        self.assertEqual([s['flag'] for s in app.signals(app.CASES[2])],[None]*5)
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

if __name__=='__main__': unittest.main()
