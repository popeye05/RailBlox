"""AI, local learning and idempotent report/monitor automation."""
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from .ai import AI, Assistance, Incident
from .domain import utcnow
from .intelligence_models import TextRequest, ReportRequest
from .security import principal
from .learning import train


class Schedule(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    interval_minutes: int = Field(default=30, ge=5, le=1440)
    prepare_reports: bool = False


class Automation:
    def __init__(self, store, lock, services, settings):
        self.store, self.lock, self.services, self.settings = store, lock, services, settings
        self.halt = threading.Event()
        self.thread = None

    def config(self):
        try:
            return self.store.get('automation-config', 'automation_config')
        except KeyError:
            return dict(id='automation-config', enabled=False, interval_minutes=30, prepare_reports=False)

    def start(self):
        self.thread = threading.Thread(target=self.loop, daemon=True, name='railblox-monitor')
        self.thread.start()

    def stop(self):
        self.halt.set()
        if self.thread:
            self.thread.join(timeout=10)

    def loop(self):
        while not self.halt.wait(15):
            try:
                config = self.config()
                if config['enabled'] and time.time() >= config.get('next_run', 0):
                    token = principal.set({'id': 'automation', 'role': 'admin', 'division': self.settings.division})
                    try:
                        self.run()
                    finally:
                        principal.reset(token)
            except Exception:
                # Failure never advances operational state; retry on the next tick.
                import logging
                logging.getLogger('railblox.automation').error('Automation tick failed; inspect database availability')

    def run(self):
        with self.lock:
            config = self.config()
            run = dict(id=str(uuid4()), created_at=utcnow(), status='running', alerts=[], report_ids=[])
            self.store.put('automation_run', run)
            try:
                for snapshot_id in self.store.heads().values():
                    workspace = self.services['workspace'](snapshot_id)
                    run['alerts'].extend({**a, 'snapshot_id': snapshot_id} for a in workspace['alerts'])
                    if config['prepare_reports']:
                        for rec in workspace['recommendations']:
                            if rec['review_status'] != 'approved' or not rec['current']:
                                continue
                            outcome_ids = sorted(o['id'] for o in workspace['outcomes'] if o['recommendation_id'] == rec['id'])
                            key = hashlib.sha256(json.dumps([rec['id'], outcome_ids]).encode()).hexdigest()
                            for kind in ('MIS', 'PAM'):
                                marker = 'automatic-' + kind + '-' + key
                                # Draft and marker are one immutable document, so crash/retry cannot duplicate it.
                                if any(r['id'] == marker for r in self.store.all('report')):
                                    continue
                                report = self.services['create_report'](ReportRequest(recommendation_id=rec['id'], kind=kind), record_id=marker)
                                run['report_ids'].append(report['id'])
                run['status'] = 'succeeded'
            except Exception:
                run['status'] = 'failed'
                run['error'] = 'Automation failed; inspect input validity and database availability. Completed drafts are retained.'
            run['completed_at'] = utcnow()
            self.store.put('automation_run', run, mutable=True)
            self.store.put('automation_config', {**config, 'next_run': time.time() + config['interval_minutes'] * 60}, mutable=True)
            self.store.audit('automation-run', run['id'], {'status': run['status'], 'reports': len(run['report_ids'])})
            return run


def platform_router(store, lock, services, automation):
    api = APIRouter(prefix='/api', tags=['AI and automation'])
    ai = AI(store)

    @api.get('/ai/status')
    def status():
        return {**ai.status(), 'optimizer': 'OR-Tools CP-SAT 9.15', 'nlp': 'Local span extraction + optional LLM',
                'automation': automation.config()}

    @api.post('/ai/recommendations/{id}/explain')
    def explain(id: str):
        r = store.get(id, 'recommendation')
        rows = [{'task_id': row['task_id'], 'priority': row['priority'], 'duration': row['duration'],
                 'action': row['action']} for row in r['rows'][:40]]
        return ai.generate('recommendation_explanation',
            {'reference': id, 'evidence_ids': [x['task_id'] for x in rows], 'work': rows,
             'solver_status': r['plan']['solver_status'], 'validation': r['plan']['validation']}, r['synthetic'], Assistance)

    @api.post('/ai/reports/{id}/summary')
    def summarize(id: str):
        r = store.get(id, 'report')
        return ai.generate('report_summary', {'reference': id, 'evidence_ids': [x['task_id'] for x in r['rows']],
            'rows': r['rows'], 'missing': r['missing'], 'status': r['recommendation_status']}, r['synthetic'], Assistance)

    @api.post('/ai/nlp/{snapshot_id}')
    def nlp(snapshot_id: str, body: TextRequest):
        services['evidence_for'](store.snapshot(snapshot_id))
        # Free text is never automatically considered synthetic merely because the workspace is synthetic.
        return ai.generate('incident_extraction', {'reference': snapshot_id, 'original': body.text}, False, Incident)

    @api.get('/ai/history')
    def history():
        return sorted(store.all('ai_call'), key=lambda x: x['created_at'], reverse=True)[:50]

    @api.post('/ai/models/{snapshot_id}/train')
    def train_model(snapshot_id: str):
        with lock:
            ws = services['workspace'](snapshot_id)
            history = ws['evidence']['history'] + [o['history'] for o in ws['outcomes']]
            model = train(history, datetime.fromisoformat(ws['evidence']['as_of']), snapshot_id)
            model['synthetic'] = ws['evidence']['synthetic']
            store.put('duration_model', model)
            store.audit('duration-model-evaluated', model['id'], {'snapshot_id': snapshot_id})
            return model

    @api.get('/ai/models')
    def models():
        return sorted(store.all('duration_model'), key=lambda x: x['created_at'], reverse=True)[:50]

    @api.get('/admin/automation')
    def automation_status():
        return {'config': automation.config(), 'runs': sorted(store.all('automation_run'), key=lambda x: x['created_at'], reverse=True)[:30]}

    @api.post('/admin/automation/config')
    def configure(body: Schedule):
        with lock:
            config = dict(id='automation-config', **body.model_dump(), next_run=time.time() + body.interval_minutes * 60)
            store.put('automation_config', config, mutable=True)
            store.audit('automation-configured', config['id'], body.model_dump())
            return config

    @api.post('/admin/automation/run')
    def run():
        return automation.run()

    return api
