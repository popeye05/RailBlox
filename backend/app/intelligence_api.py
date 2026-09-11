"""Read-only source integration and local officer-review workflow for SPEC 2."""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from .domain import utcnow
from .intelligence_models import (Evidence, EvidenceImport, RecommendRequest, DecisionRequest,
                                  OutcomeRequest, TextRequest, ReportRequest, ReportReview)
from .intelligence import (seed_evidence, validate_references, freshness, intelligence_rows,
                           planning_snapshot, alerts, extract_text, duration_diagnostics,
                           intelligence_brief)
from .solver import solve
from .footprints import eligible
from .validator import validate


def router(store, enqueue, mutation_lock, require_current, locks_for, source_head):
    api = APIRouter(prefix='/api/intelligence', tags=['Decision support'])

    def newest(snapshot_id):
        versions = [r for r in store.all('evidence') if r['snapshot_id']==snapshot_id]
        return sorted(versions,key=lambda r:r['saved_at'])[-1] if versions else None

    def evidence_for(snapshot):
        with mutation_lock:
            saved = newest(snapshot.id)
            if saved:
                return Evidence.model_validate(saved['evidence'])
            if snapshot.parent_id:
                parent = evidence_for(store.snapshot(snapshot.parent_id))
                data=parent.model_dump(mode='json'); data.update(id=str(uuid4()),snapshot_id=snapshot.id)
                data['assessments']={k:v for k,v in data['assessments'].items() if any(t.id==k for t in snapshot.tasks)}
                evidence=Evidence.model_validate(data)
            else:
                evidence=seed_evidence(snapshot)
            store.put('evidence',dict(id=evidence.id,snapshot_id=snapshot.id,saved_at=utcnow(),evidence=evidence.model_dump(mode='json')))
            return evidence

    def outcomes_for(snapshot, cutoff=None):
        rows=[o for o in store.all('outcome') if o['corridor']==snapshot.corridor]
        return [o for o in rows if not cutoff or datetime.fromisoformat(o['history']['completed_at'])<=cutoff]

    def require_evidence(snapshot, evidence_id):
        require_current(snapshot)
        evidence=evidence_for(snapshot)
        if evidence.id!=evidence_id:
            raise HTTPException(409,'Evidence changed. Refresh and recompute the recommendation.')
        bad=[f for f in freshness(evidence) if f['state']!='available']
        if bad:
            raise HTTPException(409,'Source data needs review: '+', '.join(f['source']+' '+f['state'] for f in bad))
        return evidence

    def recommendation_view(record):
        decisions=store.events(record['id'])
        status=next((e['kind'].removeprefix('recommendation-') for e in reversed(decisions)
                     if e['kind'] in ['recommendation-approved','recommendation-rejected']), 'pending')
        s=store.snapshot(record['source_snapshot_id'])
        current=(store.heads()[s.corridor]==source_head(s) and evidence_for(s).id==record['evidence_id'])
        return {**record,'review_status':status,'current':current,'events':decisions}

    @api.get('/workspace')
    def workspace(snapshot_id: str):
        snapshot=store.snapshot(snapshot_id); evidence=evidence_for(snapshot)
        outcomes=outcomes_for(snapshot,evidence.as_of)
        recommendations=[recommendation_view(r) for r in store.all('recommendation') if r['source_snapshot_id']==snapshot.id]
        outcome_rows=outcomes_for(snapshot)
        rows=intelligence_rows(snapshot,evidence,outcomes)
        current_alerts=alerts(evidence,outcome_rows)
        return dict(snapshot_id=snapshot.id,corridor=snapshot.corridor,anchor=snapshot.anchor,movements=snapshot.movements,evidence=evidence.model_dump(mode='json'),
                    feeds=freshness(evidence),rows=rows,
                    alerts=current_alerts,
                    intelligence=intelligence_brief(snapshot,evidence,rows,outcome_rows),
                    outcomes=outcome_rows,recommendations=sorted(recommendations,key=lambda r:r['created_at'],reverse=True),
                    diagnostics=duration_diagnostics(evidence.history),
                    mode='Synthetic advisory' if evidence.synthetic else 'Imported data · shadow review',
                    methods=dict(priority='Explicit weighted policy',duration='Matched empirical duration ratios',
                                 nlp='Local vocabulary/span extractor',reports='Deterministic evidence-based draft',
                                 scheduling='CP-SAT and independent constraint validation'),
                    integration='No live COA, ROAMS or weather connection. No external AI data transfer.')

    @api.get('/evidence/{snapshot_id}/sample')
    def sample(snapshot_id: str):
        evidence=evidence_for(store.snapshot(snapshot_id))
        return Response(json.dumps(evidence.model_dump(mode='json'),indent=2),media_type='application/json',
                        headers={'Content-Disposition':'attachment; filename="railblox-evidence.json"'})

    @api.post('/evidence')
    def import_evidence(body: EvidenceImport):
        with mutation_lock:
            snapshot=store.snapshot(body.evidence.snapshot_id); require_current(snapshot)
            if evidence_for(snapshot).id!=body.expected_evidence:
                raise HTTPException(409,'Evidence changed; refresh before importing')
            validate_references(body.evidence,snapshot)
            evidence=body.evidence.model_copy(update={'id':str(uuid4())})
            store.put('evidence',dict(id=evidence.id,snapshot_id=snapshot.id,saved_at=utcnow(),evidence=evidence.model_dump(mode='json')))
            store.audit('evidence-import',evidence.id,dict(previous=body.expected_evidence,actor='local-demo',synthetic=evidence.synthetic))
            return evidence

    @api.post('/recommend')
    def recommend(body: RecommendRequest):
        snapshot=store.snapshot(body.snapshot_id); evidence=require_evidence(snapshot,body.evidence_id)
        if body.task_id and not any(t.id==body.task_id for t in snapshot.tasks):
            raise ValueError('Unknown override task')
        if body.task_id and body.task_id not in {t.id for t in eligible(snapshot,body.day,body.horizon)}:
            raise ValueError('Override task is outside the selected planning horizon')
        if body.window_id and not any(w.id==body.window_id for w in snapshot.windows):
            raise ValueError('Unknown override window')
        if body.window_id and not any(w.id==body.window_id and w.start<(body.day+body.horizon)*1440 and w.end>body.day*1440 for w in snapshot.windows):
            raise ValueError('Override window is outside the selected planning horizon')
        cutoff=evidence.as_of
        rows=intelligence_rows(snapshot,evidence,outcomes_for(snapshot,cutoff))
        locks=locks_for(snapshot,body.day,body.horizon)
        if body.task_id in locks:
            raise HTTPException(409,'The selected task is locked or started; revise the commitment explicitly in Planner')
        forced={body.task_id:dict(window_id=body.window_id)} if body.task_id else None

        def operation():
            derived=planning_snapshot(snapshot,evidence,rows)
            plan=solve(derived,body.horizon,body.day,locks=locks,forced=forced)
            record_id=str(uuid4())
            plan['intelligence_id']=record_id
            assignments={a['task_id']:a for a in plan['assignments']}
            for row in rows:
                row['recommendation']=assignments.get(row['task_id'])
                row['action']='Review recommended window' if row['recommendation'] else 'No assigned window; review constraints and inputs'
            with mutation_lock:
                require_evidence(snapshot,evidence.id)
                store.save_snapshot(derived)
                store.put('plan',plan)
                store.audit('recommendation-created',record_id,dict(actor='local-demo',request=body.model_dump()))
            return dict(id=record_id,created_at=utcnow(),source_snapshot_id=snapshot.id,
                        evidence_id=evidence.id,plan_id=plan['id'],plan=plan,rows=rows,
                        synthetic=evidence.synthetic,as_of=evidence.as_of.isoformat(),
                        override=body.model_dump() if body.task_id else None,
                        methodology='Priority policy + empirical duration allowance + CP-SAT; no live execution authority')
        return enqueue('recommendation',operation)

    @api.get('/recommendations/{id}')
    def recommendation(id: str):
        return recommendation_view(store.get(id,'recommendation'))

    @api.post('/recommendations/{id}/decision')
    def decide(id: str, body: DecisionRequest):
        with mutation_lock:
            r=store.get(id,'recommendation'); s=store.snapshot(r['source_snapshot_id'])
            view=recommendation_view(r)
            if view['review_status']!='pending':
                raise HTTPException(409,'This recommendation already has a decision')
            if body.action=='approve':
                require_evidence(s,r['evidence_id'])
                plan=store.get(r['plan_id'],'plan'); derived=store.snapshot(plan['snapshot_id'])
                checked=validate(derived,plan,locks_for(derived,plan['day'],plan['horizon']))
                if not checked['valid'] or plan['solver_status'] not in ['OPTIMAL','FEASIBLE']:
                    raise HTTPException(409,'No valid feasible recommendation to approve')
            # Both events share one database transaction.
            with store.session() as session:
                store.audit('recommendation-approved' if body.action=='approve' else 'recommendation-rejected',id,
                            dict(reason=body.reason,actor='local-demo',evidence_id=r['evidence_id']),session=session)
                if body.action=='approve':
                    store.audit('approve',r['plan_id'],dict(reason=body.reason,actor='local-demo',snapshot_id=derived.id,assignments=plan['assignments']),session=session)
                session.commit()
            return recommendation_view(r)

    @api.post('/recommendations/{id}/outcomes')
    def record_outcome(id: str, body: OutcomeRequest):
        with mutation_lock:
            r=store.get(id,'recommendation')
            if recommendation_view(r)['review_status']!='approved':
                raise HTTPException(409,'Record actual outcomes against an approved demo recommendation')
            s=store.snapshot(r['source_snapshot_id'])
            if any(o['recommendation_id']==id and o['task_id']==body.task_id for o in outcomes_for(s)):
                raise HTTPException(409,'This task already has a recorded outcome')
            a=next((a for a in r['plan']['assignments'] if a['task_id']==body.task_id),None)
            if not a:
                raise ValueError('Task is not assigned in this recommendation')
            t=next(t for t in s.tasks if t.id==body.task_id)
            estimate=next(row['duration'] for row in r['rows'] if row['task_id']==t.id)
            oid=str(uuid4()); anchor=datetime.fromisoformat(s.anchor)
            history=dict(id=oid,section=t.section,department=t.department,work_class=t.work_class,
                         planned_minutes=t.duration,actual_minutes=body.actual_end-body.actual_start,
                         delay_minutes=body.delay_minutes,completed_at=(anchor+timedelta(minutes=body.actual_end)).isoformat(),
                         weather=body.weather,narrative=body.narrative)
            from .intelligence_models import History
            History.model_validate(history)
            result=dict(id=oid,created_at=utcnow(),recommendation_id=id,corridor=s.corridor,task_id=t.id,
                        predicted_high=estimate['high'],history=history,**body.model_dump(exclude={'task_id'}))
            store.put('outcome',result); store.audit('outcome-recorded',id,dict(outcome_id=oid,actor='local-demo'))
            return result

    @api.post('/nlp/{snapshot_id}')
    def nlp(snapshot_id: str, body: TextRequest):
        s=store.snapshot(snapshot_id); e=evidence_for(s)
        return extract_text(body.text,[r['id'] for r in s.sections],e.history)

    def report_view(record):
        reviews=[e for e in store.events(record['id']) if e['kind']=='report-reviewed']
        return {**record,'status':'reviewed draft' if reviews else 'draft',
                'summary':reviews[-1]['data']['summary'] if reviews else record['summary'], 'reviews':reviews}

    @api.get('/reports')
    def reports(snapshot_id: str):
        return [report_view(r) for r in sorted(store.all('report'),key=lambda r:r['created_at'],reverse=True) if r['snapshot_id']==snapshot_id]

    def create_report(body: ReportRequest, record_id: str | None = None):
        r=store.get(body.recommendation_id,'recommendation'); s=store.snapshot(r['source_snapshot_id'])
        outcomes=[o for o in outcomes_for(s) if o['recommendation_id']==r['id']]
        rows=[]; missing=[]
        for a in r['plan']['assignments']:
            t=next(t for t in s.tasks if t.id==a['task_id']); o=next((o for o in outcomes if o['task_id']==t.id),None)
            rows.append(dict(task_id=t.id,title=t.title,section=t.section,window_id=a['window_id'],
                             planned_minutes=t.duration,planning_allowance=a['end']-a['start'],
                             actual_minutes=o['history']['actual_minutes'] if o else None,
                             delay_minutes=o['delay_minutes'] if o else None,
                             source_record=t.source_record_id,narrative=o['narrative'] if o else None))
            if not o: missing.append(t.id+': actual execution outcome not recorded')
            if not t.source_record_id: missing.append(t.id+': source record ID missing')
        view=recommendation_view(r)
        if view['review_status']!='approved': missing.append('Officer recommendation approval not recorded')
        if not view['current']: missing.append('Recommendation inputs have changed')
        record=dict(id=record_id or str(uuid4()),created_at=utcnow(),snapshot_id=s.id,recommendation_id=r['id'],
                    evidence_id=r['evidence_id'],anchor=s.anchor,kind=body.kind,rows=rows,missing=missing,
                    recommendation_status=view['review_status'],synthetic=r['synthetic'],
                    summary=f"{body.kind} draft for {s.name}: {len(rows)} assigned work items in {len(r['plan']['packages'])} packages. "
                            f"{len(outcomes)} actual outcomes recorded; {len(missing)} items need review. "
                            f"Recommendation decision: {view['review_status']}. Figures are derived from saved records.",
                    method='Deterministic local summary; illustrative MIS/PAM fields, not an official return')
        store.put('report',record); store.audit('report-drafted',record['id'],dict(actor='local-demo'))
        return report_view(record)

    @api.post('/reports')
    def draft_report(body: ReportRequest):
        return create_report(body)

    @api.post('/reports/{id}/review')
    def review_report(id: str, body: ReportReview):
        record=store.get(id,'report')
        store.audit('report-reviewed',id,dict(**body.model_dump(),actor='local-demo'))
        return report_view(record)

    @api.get('/reports/{id}/export')
    def export_report(id: str):
        return Response(json.dumps(report_view(store.get(id,'report')),indent=2),media_type='application/json',
                        headers={'Content-Disposition':f'attachment; filename="railblox-draft-{id}.json"'})

    api.services=dict(workspace=workspace,evidence_for=evidence_for,create_report=create_report,
                      recommend=recommend,report_view=report_view)
    return api
