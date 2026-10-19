"""Build the install-free browser demo from the tested Python prototype."""
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parent
source=root.parent  # repo root holds app.py / index.html
spec=importlib.util.spec_from_file_location('gc_source',source/'app.py')
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
cases=[{**c,'signals':app.signals(c)} for c in app.CASES]
(root/'dist/cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
html=(source/'index.html').read_text(encoding='utf-8')
html=html.replace('GC Audit Assist · 계속기업 검토','GC Audit Assist · 팀 시연')
html=html.replace('FIRST REVIEW PROTOTYPE','ONLINE TEAM DEMO')
html=html.replace('가상자료 시연 모드','설치 없는 시연')
html=html.replace('<div class="notice">','<div class="notice">입력은 현재 기기·브라우저에만 저장됩니다. 다른 팀원에게 보이지 않으며 브라우저 데이터를 삭제하면 사라집니다. 가상 내용만 입력하세요.<br>')
html=html.replace('로컬 시제품 v0.1 · 데이터는 이 컴퓨터에 저장됩니다. 사용자 인증·다중 사용자 권한·실제 증거 첨부는 후속 범위입니다.','온라인 시연 v0.1 · 기록은 현재 브라우저에 저장됩니다. 팀 공동 편집·실제 증거 첨부는 후속 범위입니다. <a href="./guide.html">팀 안내와 다음 작업</a>')
html=html.replace('<script>','<script src="./demo-engine.js"></script>\n<script>\nlet demo;')
html=html.replace("async function load(){const r=await fetch('/api/state');if(!r.ok)throw Error('자료를 불러올 수 없습니다.');state=await r.json()}","async function load(){if(!demo){const r=await fetch('./cases.json');if(!r.ok)throw Error('시연 자료를 불러올 수 없습니다.');demo=createAuditDemo(await r.json(),localStorage);}state=demo.read()}")
html=html.replace("await fetch('/api/save'","await demo.request('/api/save'")
html=html.replace("await fetch('/api/custom-case'","await demo.request('/api/custom-case'")
html=html.replace("await fetch('/api/export?case='","await demo.request('/api/export?case='")
assert "fetch('/api/" not in html
(root/'dist/index.html').write_text(html,encoding='utf-8')

