"""Customer-path publication contracts; EC2-only, no SDK execution."""
import ast
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]
m=json.loads((root/'docs/site-publication.json').read_text());version=m['sdk_version']
qualified_version=m.get('qualified_sdk_version',version)
active=['docs/start-here.md','docs/operations/wheel-install.md','docs/implementation/video-profiles.md','docs/README.ru.md']
for name in active:
    text=(root/name).read_text()
    wheels=re.findall(r'ariadne_mark-([0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?)-py3-none-any\.whl',text)
    assert wheels and all(x==version for x in wheels),(name,wheels,version)
report_ast=ast.parse((root/'src/ariadne_mark/verification/media.py').read_text())
schema=next(n.value.value for n in ast.walk(report_ast) if isinstance(n,ast.Assign)
    and any(isinstance(x,ast.Name) and x.id=='REPORT_SCHEMA_VERSION' for x in n.targets))
for name in ['docs/implementation/verification-results.md','docs/reference/api-cli.md']:
    text=(root/name).read_text()
    assert 'unreleased' not in text and str(schema) in text,name
text=(root/'docs/implementation/integration.md').read_text()
assert 'share one resident Node worker per SDK' in text
assert 'Multiple active profile workers' not in text
legal=json.loads((root/'docs/compliance/requirements-matrix.json').read_text())
assert str(json.loads((root/f'docs/validation/results/{qualified_version}-summary.json').read_text())['full_media']['tests']) in legal['rows'][0]['evidence']
cost=json.loads((root/'docs/examples/cost-workload.json').read_text());w=cost['workload'];n=w['days']*(w['images_per_day']+w['videos_per_day'])
assert n==cost['computed_base']['exports']==39000
assert 365*(w['images_per_day']+w['videos_per_day'])==cost['computed_base']['year_365_days']==474500
assert all(x is None for k,x in cost['operator_inputs'].items() if k!='video_full_job_cpu_seconds_by_profile')
for key in ['trufo_starter','trufo_business']:
    v=cost['vendor_reference'][key]
    assert v['base_usd_month']+max(0,n-v['included_signatures_month'])*v['excess_signature_usd']==v['signature_component_usd_at_base_workload']
    assert v['watermark_overage_usd'] is None
for name in ['docs/examples/export_jobs.py','scripts/ci_client_journey.py']:
    ast.parse((root/name).read_text(),filename=name)
assets={x['source'] for x in m['assets']}
assert {'docs/examples/export_jobs.py','docs/examples/jobs.example.json','docs/examples/cost-workload.json'} <= assets
print(json.dumps(dict(status='passed',sdk_version=version,report_schema=schema,
    active_install_guides=len(active),workload_exports=n,unknown_costs_preserved=True,
    runtime_rebuilt=False),indent=2))
