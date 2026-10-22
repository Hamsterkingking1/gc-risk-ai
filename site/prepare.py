"""Build the install-free browser demo from the tested Python prototype."""
import sys
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parent
source=root.parent  # repo root holds app.py / index.html
sys.path.insert(0,str(source))
spec=importlib.util.spec_from_file_location('gc_source',source/'app.py')
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
cases=[{**c,'signals':app.signals(c)} for c in app.CASES]
cases_json=json.dumps(cases,ensure_ascii=False,indent=2)
(root/'dist/cases.json').write_text(cases_json,encoding='utf-8')
html=(source/'index.html').read_text(encoding='utf-8')
html=html.replace('GC Audit Assist · 계속기업 검토','GC Audit Assist · 팀 시연')
html=html.replace('FIRST REVIEW PROTOTYPE','ONLINE TEAM DEMO')
html=html.replace('OpenDART 공시 연동 모드','설치 없는 온라인 시연')
html=html.replace('<div class="notice">','<div class="notice">입력은 현재 기기·브라우저에만 저장됩니다. 다른 팀원에게 보이지 않으며 브라우저 데이터를 삭제하면 사라집니다.<br>')
html=html.replace('로컬 시제품 v0.1 · 데이터는 이 컴퓨터에 저장됩니다. 사용자 인증·다중 사용자 권한·실제 증거 첨부는 후속 범위입니다.','온라인 시연 v0.4 · 공시 원문 3개년 대조 · 기록은 현재 브라우저에 저장됩니다. <a href="./guide.html">팀 안내와 다음 작업</a> · <a href="./source-review.html">기업별 원문 대조표</a>')
html=html.replace('<script>',f'<script src="./quality.js?v=4"></script>\n<script src="./demo-engine.js?v=4"></script>\n<script>\nwindow.INLINE_CASES={cases_json};\nlet demo;')
html=html.replace("async function load(){const r=await fetch('/api/state');if(!r.ok)throw Error('자료를 불러올 수 없습니다.');state=await r.json()}","async function load(){if(!demo){let cs=window.INLINE_CASES;if(!cs){const r=await fetch('./cases.json');if(!r.ok)throw Error('시연 자료를 불러올 수 없습니다.');cs=await r.json();}demo=createAuditDemo(cs,localStorage);}state=demo.read()}")
html=html.replace("await fetch('/api/save'","await demo.request('/api/save'")
html=html.replace("await fetch('/api/custom-case'","await demo.request('/api/custom-case'")
html=html.replace("await fetch('/api/export?case='","await demo.request('/api/export?case='")
assert "fetch('/api/" not in html
(root/'dist/index.html').write_text(html,encoding='utf-8')
import html as html_lib
e=html_lib.escape
table=[]
for c in cases:
    for y,a in c.get('annual_financials',{}).items():
        audit=c['audit_by_year'][y]
        display=lambda k:format(__import__('decimal').Decimal(a[k])/1000000,'f')
        cells=[c['name'],y,*[display(k) for k in ('assets','liabilities','due','debt')],
               '있음' if audit['flag'] else '해당 단락 없음',audit['opinion']]
        table.append('<tr>'+''.join('<td>'+e(v)+'</td>' for v in cells)+f'<td><a href="{e(c["links"][y])}" target="_blank" rel="noopener">공시 원문</a></td></tr>')
warnings=list(dict.fromkeys(w for c in cases for w in c.get('source_warnings',[])))
review='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>5개 기업 공시 원문 대조표</title><style>body{font-family:system-ui,sans-serif;margin:32px;color:#153743;background:#f4f8f8}main{max-width:1500px;margin:auto;background:white;padding:28px;border-radius:16px}table{border-collapse:collapse;min-width:1100px;width:100%;font-size:14px}th,td{padding:12px;border-bottom:1px solid #d6e1e1;text-align:left}th{background:#e8f2f0}li{margin:12px 0}a{color:#007b83}</style><main><a href="./index.html">← 감사보조 도구로 돌아가기</a><h1>5개 기업 · 3개년 공시 원문 대조표</h1><p>확인일: 2026-10-22 · 별도재무제표 · 금액: 백만원 · 차입금은 리스 제외 장부금액</p><div style="overflow:auto"><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in ('기업','연도','유동자산','유동부채','유동 차입금·사채','총차입금·사채','기업 고유 계속기업 문구','감사의견','출처'))+'</tr></thead><tbody>'+''.join(table)+'</tbody></table></div><h2>자료 사용 시 확인할 사항</h2><ul>'+''.join('<li>'+e(w)+'</li>' for w in warnings)+'</ul><p>공시 링크에서 첨부된 별도 감사보고서를 선택하면 재무제표와 주석을 확인할 수 있습니다. 수치 대조는 감사판단을 대신하지 않습니다.</p></main></html>'
(root/'dist/source-review.html').write_text(review,encoding='utf-8')
import shutil
docs=source/'docs'
docs.mkdir(exist_ok=True)
for item in (root/'dist').iterdir():
    if item.is_file():
        shutil.copy2(item, docs/item.name)


