"""Opt-in live provider smoke; synthetic input only, no database or saved-project writes.

Run: .venv/Scripts/python.exe -m tests.live_report_smoke
"""
import json
import time
from pathlib import Path
from app.services.gemini_service import GeminiService
from app.workflows.shift_graph import build_graph
from app.services.report_service import assemble_report
from app.core.errors import AppError


def main():
    context = {'project': {'name':'Synthetic warehouse dispatch pilot', 'industry':'Retail distribution',
        'initial_problem':'Dispatch staff copy confirmed orders from a CSV into a shipping worksheet. Fixed postcode and package-weight rules identify incomplete orders. Reduce retyping while a supervisor reviews exceptions; no AI prediction or automated payments are needed.'},
        'output_language':'English', 'messages':[{'id':'synthetic-user-1','role':'user','content':
        'Four dispatch staff process a daily CSV. A supervisor approves shipments; invalid addresses need manual correction. Keep the order system as source of truth. CSV import/export is available; no vendor API is confirmed. One Python engineer can build a pilot. Budget, rates, location, baseline timings and vendor quotes are unknown. Prefer simple hosting and human review. Validate mappings, privacy, retention and rollback with operations.'}],
        'previous_discovery':None, 'documents':[], 'evidence':[], 'retrieval_warnings':[]}
    started = time.monotonic()
    def progress(stage, state):
        print('Stage:',stage,'elapsed:',round(time.monotonic()-started),'seconds',flush=True)
    try:
        result = build_graph(GeminiService(),progress).invoke({'context':context,'red_team_cycle':0,'red_team_history':[]}, {'recursion_limit':30})
        result['evidence'] = [{'category':'workflow','fact':context['messages'][0]['content'],'source':'synthetic-user-1'}]
        result['final_report'] = assemble_report(result, context)
        output = Path(__file__).resolve().parents[2] / 'tmp' / 'report-review'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'live-warehouse-report.json').write_text(json.dumps({k:v for k,v in result.items() if k!='context'},ensure_ascii=False,indent=2),encoding='utf-8')
        print('PASS: live warehouse report;',len(result['final_report']['sections']),'sections; selected:',result['option_decision']['selected'],flush=True)
        return 0
    except AppError as exc:
        print('LIVE_CHECK_UNAVAILABLE:',exc.code,exc.message,flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
