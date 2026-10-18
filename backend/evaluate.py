"""Reproducible retrieval checks; --live also collects real model outputs for review."""
import argparse
import json
import os
import tempfile
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--live',action='store_true',help='Calls your configured paid model for every supported question.')
args=parser.parse_args()
if args.live and not (os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')):
    parser.error('--live requires OPENAI_API_KEY and OPENAI_MODEL in your environment')
if not args.live: os.environ.pop('OPENAI_API_KEY',None)
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    os.environ['DATABASE_URL']='sqlite:///'+str(Path(temp)/'evaluation.db')
    from app.db import Session, init_db, engine
    from app.pipeline import ingest
    from app.rag import answer
    init_db();ingest()
    cases=json.loads((ROOT/'evaluation/cases.json').read_text())
    results=[]
    with Session() as db:
        for case in cases:
            r=answer(db,case['question'],patch=case.get('patch'))
            source_hit=any(c['source']==case.get('source') for c in r['citations'])
            expected_present=all(term.lower() in r['answer'].lower() for term in case.get('expected_terms',[]))
            passed=r['abstained'] if case.get('abstain') else source_hit and expected_present and not r['abstained']
            item={'question':case['question'],'passed':passed,'abstained':r['abstained'],'sources':[c['source'] for c in r['citations']],'expected_terms_present':expected_present,'latency_ms':r['latency_ms']}
            if args.live: item.update(answer=r['answer'],usage=r['usage'],mode=r['mode'],human_review={'factual_correctness':None,'citation_support':None,'patch_consistency':None})
            results.append(item)
    engine.dispose()
report={'scope':'Live-model lexical checks plus manual review required.' if args.live else 'Offline retrieval, expected-term coverage and abstention on editorial summaries. Not a live LLM accuracy benchmark.', 'passed':sum(r['passed'] for r in results),'total':len(results),'cases':results}
filename='live-report.json' if args.live else 'report.json'
(ROOT/'evaluation'/filename).write_text(json.dumps(report,indent=2))
print(f"{report['passed']}/{report['total']} checks passed. Report: evaluation/{filename}")
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
