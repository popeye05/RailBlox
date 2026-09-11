import csv
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from uuid import uuid4
from pathlib import Path
from contextvars import copy_context
from .security import Settings, install_security, principal
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlalchemy import text
from .domain import Task, Snapshot, Window, PlanOutput, TaskPage, ValidationOutput, RunOutput, GenerateRequest, RevisionRequest, ApprovalRequest, ScenarioRequest, utcnow
from .persistence import Store
from .fixtures import acceptance, presentation
from .solver import solve
from .validator import validate
from .repair import scenario_snapshot
from .candidates import discover
from .adapters import preview, safe_csv, SOURCES, LIMIT
from .benchmarks import benchmark


class EditTask(BaseModel):
    expected_snapshot: str
    task: Task


class MappingRequest(BaseModel):
    expected_snapshot: str
    asset_id: str


class CommitRequest(BaseModel):
    expected_snapshot: str
    mapping_confirmed: bool


class OpportunityRequest(BaseModel):
    window_id: str


def create_app(database_url=None):
    settings=Settings.load()
    store=Store(database_url); executor=ThreadPoolExecutor(max_workers=1); mutation_lock=threading.RLock()

    @asynccontextmanager
    async def lifespan(app):
        lease=None
        if settings.environment=='production':
            lease=store.engine.connect()
            if not lease.execute(text('SELECT pg_try_advisory_lock(724196310)')).scalar():
                lease.close()
                raise RuntimeError('Only one API process may own this deployment database')
        store.init()
        for fixture in ([acceptance,presentation] if os.getenv('SEED_DEMO','true' if settings.environment=='development' else 'false').lower()=='true' else []):
            snapshot=fixture()
            if snapshot.corridor not in store.heads():
                store.save_snapshot(snapshot,head=True)
                store.put('plan',solve(snapshot,core_only=True))
        automation.start()
        try:
            yield
        finally:
            automation.stop()
            executor.shutdown(wait=True)
            if lease is not None:
                lease.execute(text('SELECT pg_advisory_unlock(724196310)')); lease.close()

    app=FastAPI(title='RaILBLOX decision support',version='0.2.0',lifespan=lifespan,
                docs_url=None if settings.environment=='production' else '/docs',
                openapi_url=None if settings.environment=='production' else '/openapi.json',redoc_url=None)
    app.state.store=store
    import os
    install_security(app,settings,store)
    app.add_middleware(CORSMiddleware,allow_origins=list(settings.origins),allow_methods=['GET','POST','PATCH'],allow_headers=['Content-Type','Authorization'],expose_headers=['Content-Disposition','X-Request-ID'])

    def error(request,code,message,status,details=None):
        return JSONResponse(status_code=status,content=dict(code=code,message=message,details=details,request_id=getattr(request.state,'request_id',str(uuid4()))))

    @app.exception_handler(KeyError)
    async def missing(request,exc): return error(request,'NOT_FOUND','Record not found',404,str(exc))

    @app.exception_handler(ValueError)
    async def invalid(request,exc): return error(request,'STALE_SNAPSHOT' if str(exc)=='STALE_SNAPSHOT' else 'INVALID_INPUT',str(exc),409 if str(exc)=='STALE_SNAPSHOT' else 422)

    @app.exception_handler(RequestValidationError)
    async def schema_error(request,exc): return error(request,'INVALID_INPUT','Check the supplied fields',422,json.loads(json.dumps(exc.errors(),default=str)))

    @app.exception_handler(HTTPException)
    async def http_error(request,exc): return error(request,'CONFLICT' if exc.status_code==409 else 'REQUEST_REJECTED',str(exc.detail),exc.status_code)

    def source_head(snapshot):
        current=snapshot
        while current.scenario and current.parent_id: current=store.snapshot(current.parent_id)
        return current.id

    def require_current(snapshot,expected=None):
        if expected and snapshot.id!=expected: raise ValueError('STALE_SNAPSHOT')
        if store.heads()[snapshot.corridor]!=source_head(snapshot): raise ValueError('STALE_SNAPSHOT')

    def locks_for(snapshot,day=0,horizon=30):
        released={e['data']['plan_id'] for e in store.events() if e['kind']=='release'}
        locks={}
        for e in store.events():
            if e['kind']=='approve' and e['record_id'] not in released:
                p=store.get(e['record_id'],'plan'); s=store.snapshot(p['snapshot_id'])
                if s.corridor==snapshot.corridor:
                    for a in p['assignments']:
                        if day*1440<=a['start']<(day+horizon)*1440: locks[a['task_id']]=a
        started={t.id for t in snapshot.tasks if t.started}
        for p in sorted(store.all('plan'),key=lambda p:p['created_at']):
            if store.snapshot(p['snapshot_id']).corridor==snapshot.corridor:
                for a in p['assignments']:
                    if a['task_id'] in started: locks.setdefault(a['task_id'],a)
        return locks

    def plan_view(plan):
        snapshot=store.snapshot(plan['snapshot_id']); events=store.events(plan['id'])
        approved=any(e['kind']=='approve' for e in events)
        released=any(e['kind']=='release' and e['data']['plan_id']==plan['id'] for e in store.events())
        current=store.heads()[snapshot.corridor]==source_head(snapshot)
        checked=validate(snapshot,plan,locks_for(snapshot,plan['day'],plan['horizon']))
        return {**plan,'validation':checked,'approval':'released' if released else 'approved' if approved else 'proposed','current':current,'events':events}

    def enqueue(kind,operation):
        with mutation_lock:
            if any(r['status'] in ['queued','running'] for r in store.all('run')): raise HTTPException(409,'A job is already active. Wait for it to finish.')
            run=dict(id=str(uuid4()),kind=kind,status='queued',created_at=utcnow(),actor=principal.get()['id']); store.put('run',run)
        def worker():
            try:
                store.put('run',{**run,'status':'running'},mutable=True)
                result=operation(); result.setdefault('id',str(uuid4())); result.setdefault('created_at',utcnow()); store.put('plan' if kind in ['generate','repair','revise'] else kind,result)
                store.put('run',{**run,'status':'succeeded','result_id':result['id'],'completed_at':utcnow()},mutable=True)
            except Exception as exc:
                store.put('run',{**run,'status':'failed','error':str(exc) if isinstance(exc,(ValueError,HTTPException)) else 'Background operation failed; contact the administrator with the run ID.','completed_at':utcnow()},mutable=True)
        executor.submit(copy_context().run,worker)
        return JSONResponse(status_code=202,content=run)

    @app.get('/health')
    def health(): return {'status':'ok'}

    @app.get('/ready')
    def ready():
        with store.engine.connect() as connection: connection.execute(text('SELECT 1'))
        return {'status':'ready','solver':'OR-Tools CP-SAT','rule_version':'SYNTHETIC-1'}

    @app.get('/api/context')
    def context():
        snapshots=[store.snapshot(sid) for sid in store.heads().values()]
        return dict(corridors=[dict(id=s.corridor,name=s.name,snapshot_id=s.id,anchor=s.anchor,created_at=s.created_at) for s in snapshots],plans=sorted([dict(id=p['id'],snapshot_id=p['snapshot_id'],corridor=store.snapshot(p['snapshot_id']).corridor,created_at=p['created_at'],horizon=p['horizon'],day=p['day'],solver_status=p['solver_status'],parent_id=p['parent_id']) for p in store.all('plan')],key=lambda p:p['created_at'],reverse=True),scenarios=store.all('scenario'),timezone='Asia/Kolkata')

    @app.get('/api/snapshots/{id}',response_model=Snapshot)
    def snapshot_get(id:str): return store.snapshot(id)

    @app.get('/api/tasks',response_model=TaskPage)
    def tasks(snapshot_id:str,search:str='',page:int=1,page_size:int=100):
        values=[t.model_dump() for t in store.snapshot(snapshot_id).tasks if search.lower() in (t.title+' '+t.id).lower()]
        size=min(max(page_size,1),200); offset=(max(page,1)-1)*size
        return dict(items=values[offset:offset+size],total=len(values),page=page,page_size=size)

    @app.get('/api/tasks/{id}/history')
    def task_history(id:str,snapshot_id:str):
        source=store.snapshot(snapshot_id)
        if not any(t.id==id for t in source.tasks): raise KeyError(id)
        history=[]
        for p in sorted(store.all('plan'),key=lambda p:p['created_at'],reverse=True):
            s=store.snapshot(p['snapshot_id'])
            if s.corridor!=source.corridor or not any(t.id==id for t in s.tasks): continue
            assignment=next((a for a in p['assignments'] if a['task_id']==id),None)
            reason=next((a['reason'] for a in p['unscheduled'] if a['task_id']==id),None)
            history.append(dict(plan_id=p['id'],snapshot_id=s.id,anchor=s.anchor,created_at=p['created_at'],solver_status=p['solver_status'],assignment=assignment,reason=reason))
        return dict(task_id=id,plans=history,events=store.events(id))

    @app.get('/api/benchmarks')
    def benchmark_history(snapshot_id:str):
        s=store.snapshot(snapshot_id)
        return sorted([r for r in store.all('benchmark') if store.snapshot(r['snapshot_id']).corridor==s.corridor],key=lambda r:r.get('created_at',''),reverse=True)

    def edit_task(body,existing_id=None):
        with mutation_lock:
            s=store.snapshot(body.expected_snapshot); require_current(s)
            if s.scenario: raise HTTPException(409,'Edit source tasks from the baseline workspace')
            t=body.task
            if existing_id and t.id!=existing_id: raise ValueError('Task ID cannot change')
            if existing_id and not any(x.id==existing_id for x in s.tasks): raise KeyError(existing_id)
            if not existing_id and any(x.id==t.id for x in s.tasks): raise HTTPException(409,'Task ID already exists')
            if t.id in locks_for(s) or any(x.id==t.id and x.started for x in s.tasks): raise HTTPException(409,'Release eligible approval commitments before editing; started work cannot be changed')
            asset=next((a for a in s.assets if a['id']==t.asset_id),None)
            if not asset or (asset['section'],asset['line'],asset['chainage_m'])!=(t.section,t.line,t.chainage_m): raise ValueError('Select matching canonical asset, section, line and chainage')
            if not set(t.resources)<={r.id for r in s.resources}: raise ValueError('Unknown resources')
            if not set(t.predecessors)<={x.id for x in s.tasks if x.id!=t.id}: raise ValueError('Unknown or self predecessor')
            if t.started and not any(a['task_id']==t.id for p in store.all('plan') if p['snapshot_id']==s.id for a in p['assignments']): raise ValueError('Started task needs an existing assignment')
            old=s.id; s.id=str(uuid4()); s.parent_id=old; s.created_at=utcnow(); s.tasks=[x for x in s.tasks if x.id!=t.id]+[t]
            store.save_snapshot(s,head=True,expected=old); store.audit('task_edit',t.id,dict(snapshot_id=s.id,previous_snapshot=old,task=t.model_dump()))
            return dict(snapshot_id=s.id,task=t)

    @app.post('/api/tasks')
    def task_add(body:EditTask): return edit_task(body)

    @app.patch('/api/tasks/{id}')
    def task_edit(id:str,body:EditTask): return edit_task(body,id)

    @app.get('/api/corridors/{id}/topology')
    def topology(id:str,snapshot_id:str):
        s=store.snapshot(snapshot_id)
        if s.corridor!=id: raise ValueError('Corridor does not match snapshot')
        return dict(sections=s.sections,assets=s.assets)

    @app.get('/api/windows',response_model=list[Window])
    def windows(snapshot_id:str,day:int=0,horizon:int=7): return [w for w in store.snapshot(snapshot_id).windows if day*1440<=w.start<(day+horizon)*1440]

    @app.get('/api/movements')
    def movements(snapshot_id:str,day:int=0,horizon:int=7): return [m for m in store.snapshot(snapshot_id).movements if any(day*1440<=o['start']<(day+horizon)*1440 for o in m['occupancies'])]

    @app.post('/api/plans/generate',responses={202:{'model':RunOutput}})
    def generate(body:GenerateRequest):
        s=store.snapshot(body.snapshot_id); require_current(s)
        locks=locks_for(s,body.day,body.horizon)
        return enqueue('generate',lambda:solve(s,body.horizon,body.day,locks=locks,core_only=body.core_only))

    @app.get('/api/runs/{id}',response_model=RunOutput)
    def run(id:str): return store.get(id,'run')

    @app.get('/api/plans',response_model=list[PlanOutput])
    def plans(): return [plan_view(p) for p in store.all('plan')]

    @app.get('/api/plans/{id}',response_model=PlanOutput)
    def plan(id:str): return plan_view(store.get(id,'plan'))

    @app.post('/api/plans/{id}/validate',response_model=ValidationOutput)
    def validate_plan(id:str):
        p=store.get(id,'plan'); s=store.snapshot(p['snapshot_id']); result=validate(s,p,locks_for(s,p['day'],p['horizon']))
        store.audit('validate',id,result); return {**result,'current':plan_view(p)['current']}

    @app.post('/api/plans/{id}/opportunities')
    def opportunities(id:str,body:OpportunityRequest):
        p=store.get(id,'plan'); s=store.snapshot(p['snapshot_id']); require_current(s)
        return enqueue('opportunities',lambda:discover(s,p,body.window_id,locks_for(s,p['day'],p['horizon'])))

    @app.get('/api/opportunities/{id}')
    def opportunity_result(id:str): return store.get(id,'opportunities')

    @app.post('/api/plans/{id}/revise')
    def revise(id:str,body:RevisionRequest):
        with mutation_lock:
            p=store.get(id,'plan'); s=store.snapshot(p['snapshot_id']); require_current(s,body.expected_snapshot)
            fixed={a['task_id']:a for a in p['assignments']}; locks=locks_for(s,p['day'],p['horizon'])
            if body.release_unstarted:
                started={t.id for t in s.tasks if t.started}
                locks={k:v for k,v in locks.items() if k in started}; fixed=locks.copy()
            forced={}
            if body.task_id:
                if body.task_id in locks: raise HTTPException(409,'Task is locked or started')
                if body.start is None or not body.window_id: raise ValueError('Move requires window and start minute')
                forced[body.task_id]=dict(window_id=body.window_id,start=body.start); fixed.pop(body.task_id,None)
            for tid in body.task_ids:
                if tid in locks: raise HTTPException(409,'Candidate is locked')
                if not any(t.id==tid for t in s.tasks): raise ValueError('Unknown candidate task')
                if not body.window_id: raise ValueError('Addition requires package window')
                forced[tid]=dict(window_id=body.window_id); fixed.pop(tid,None)
            fixed.update(locks)
            def operation():
                result=solve(s,p['horizon'],p['day'],baseline=p,locks=fixed,forced=forced,allowed=None if body.release_unstarted else set(fixed)|set(forced))
                if not result['validation']['valid']: raise ValueError('Revision rejected: '+json.dumps(result['validation']['violations']))
                if body.release_unstarted:
                    with mutation_lock:
                        require_current(s,body.expected_snapshot)
                        for event in store.events():
                            if event['kind']=='approve':
                                approved=store.get(event['record_id'],'plan')
                                if store.snapshot(approved['snapshot_id']).corridor==s.corridor:
                                    store.audit('release',result['id'],dict(plan_id=approved['id'],reason='Validated explicit revision of eligible unstarted commitments'))
                store.audit('revise',result['id'],body.model_dump()); return result
            return enqueue('revise',operation)

    @app.post('/api/plans/{id}/approve',response_model=PlanOutput)
    def approve(id:str,body:ApprovalRequest):
        with mutation_lock:
            p=store.get(id,'plan'); s=store.snapshot(p['snapshot_id']); require_current(s,body.expected_snapshot)
            ancestor=s
            while ancestor.parent_id and not (ancestor.scenario and ancestor.scenario.get('kind')=='intelligence'):
                ancestor=store.snapshot(ancestor.parent_id)
            if p.get('intelligence_id') or (ancestor.scenario and ancestor.scenario.get('kind')=='intelligence'):
                raise HTTPException(409,'Review this evidence-based recommendation in Block queue so the decision and evidence are recorded together')
            if plan_view(p)['approval']=='approved': raise HTTPException(409,'Proposal is already approved')
            result=validate(s,p,locks_for(s,p['day'],p['horizon']))
            if not result['valid'] or p['solver_status'] not in ['OPTIMAL','FEASIBLE']: raise HTTPException(409,'Approval blocked by modeled conflicts or no feasible solver result')
            store.audit('approve',id,dict(reason=body.reason,snapshot_id=s.id,actor='local-demo',assignments=p['assignments']))
            return plan_view(p)

    @app.post('/api/plans/{id}/finalize')
    def finalize(id:str,body:ApprovalRequest):
        with mutation_lock:
            p=store.get(id,'plan'); s=store.snapshot(p['snapshot_id']); require_current(s,body.expected_snapshot)
            if any(e['kind']=='finalize' for e in store.events(id)): raise HTTPException(409,'This cycle is already finalized')
            if s.scenario: raise HTTPException(409,'Finalize a baseline planning cycle')
            ids={t['task_id'] for t in p['unscheduled']}
            old=s.id; s.id=str(uuid4()); s.parent_id=old
            for t in s.tasks:
                if t.id in ids: t.deferrals+=1
            store.save_snapshot(s,head=True,expected=old); store.audit('finalize',id,dict(reason=body.reason,task_ids=sorted(ids),snapshot_id=s.id))
            return dict(snapshot_id=s.id)

    @app.post('/api/scenarios')
    def scenario(body:ScenarioRequest):
        with mutation_lock:
            p=store.get(body.baseline_id,'plan'); s=store.snapshot(p['snapshot_id']); require_current(s)
            changed=scenario_snapshot(s,body); store.save_snapshot(changed)
            row=dict(id=changed.id,baseline_id=p['id'],snapshot_id=changed.id,change=changed.scenario,created_at=utcnow())
            store.put('scenario',row); store.audit('scenario',row['id'],row['change']); return row

    @app.post('/api/scenarios/{id}/repair')
    def repair(id:str):
        scenario=store.get(id,'scenario'); p=store.get(scenario['baseline_id'],'plan'); s=store.snapshot(id); require_current(s)
        return enqueue('repair',lambda:solve(s,p['horizon'],p['day'],baseline=p,locks=locks_for(s,p['day'],p['horizon'])))

    @app.get('/api/scenarios/{id}')
    def get_scenario(id:str): return store.get(id,'scenario')

    @app.post('/api/imports/preview')
    async def import_preview(file:UploadFile=File(...),source:str=Form(...),snapshot_id:str=Form(...)):
        s=store.snapshot(snapshot_id); require_current(s)
        content=await file.read(LIMIT+1)
        record=preview(content,file.filename or '',source,s); store.put('import',record); return record

    @app.post('/api/imports/{id}/commit')
    def import_commit(id:str,body:CommitRequest):
        with mutation_lock:
            record=store.get(id,'import')
            if record['committed']: return record['summary']
            s=store.snapshot(body.expected_snapshot); require_current(s)
            if record['snapshot_id']!=s.id: raise ValueError('STALE_SNAPSHOT')
            if s.scenario: raise ValueError('Import into the baseline workspace')
            if not body.mapping_confirmed: raise ValueError('Confirm the illustrative column mapping first')
            items={t.id:t for t in s.tasks}; inserts=updates=unchanged=0
            for row in record['rows']:
                if row['errors']: continue
                t=Task.model_validate(row['canonical']); previous=next((x for x in items.values() if x.source==t.source and x.source_record_id==t.source_record_id),None)
                if previous:
                    t.id=previous.id
                    if previous.verified and not t.verified:
                        mapping=next((e for e in reversed(store.events(t.id)) if e['kind']=='mapping'),None)
                        keys=['asset_id','section','line','chainage_m']
                        if mapping and all(t.model_dump()[key]==mapping['data']['raw'][key] for key in keys):
                            t.asset_id=previous.asset_id; t.section=previous.section; t.line=previous.line; t.chainage_m=previous.chainage_m; t.isolation=previous.isolation; t.verified=True
                    if previous.model_dump()==t.model_dump(): unchanged+=1; continue
                    if t.id in locks_for(s): raise HTTPException(409,'Imported update would change locked work')
                    updates+=1
                else: inserts+=1
                items[t.id]=t
            old=s.id
            if inserts or updates:
                s.id=str(uuid4()); s.parent_id=old; s.created_at=utcnow(); s.tasks=list(items.values()); store.save_snapshot(s,head=True,expected=old)
            summary=dict(snapshot_id=s.id,inserts=inserts,updates=updates,unchanged=unchanged,rejected=sum(bool(r['errors']) for r in record['rows']),unresolved=sum(not t.verified for t in s.tasks))
            store.put('import',{**record,'committed':True,'summary':summary},mutable=True); store.audit('import',id,summary); return summary

    @app.get('/api/imports')
    def imports(): return store.all('import')

    @app.get('/api/mappings')
    def mappings(snapshot_id:str):
        s=store.snapshot(snapshot_id)
        return [dict(id=t.id,task=t,candidates=[a for a in s.assets if a['section']==t.section]) for t in s.tasks if not t.verified]

    @app.post('/api/mappings/{id}/resolve')
    def resolve(id:str,body:MappingRequest):
        with mutation_lock:
            s=store.snapshot(body.expected_snapshot); require_current(s)
            if s.scenario: raise ValueError('Resolve mappings in the baseline workspace')
            t=next((t for t in s.tasks if t.id==id),None); a=next((a for a in s.assets if a['id']==body.asset_id and a['verified']),None)
            if not t or not a: raise ValueError('Unknown task or unverified canonical asset')
            if t.id in locks_for(s) or t.started: raise HTTPException(409,'Cannot remap locked or started work')
            if t.verified: raise HTTPException(409,'Mapping is already confirmed; use a validated task edit for changes')
            old=s.id; raw=t.model_dump(); t.asset_id=a['id']; t.section=a['section']; t.line=a['line']; t.chainage_m=a['chainage_m']; t.isolation=a['isolation']; t.verified=True
            s.id=str(uuid4()); s.parent_id=old; s.created_at=utcnow(); store.save_snapshot(s,head=True,expected=old)
            store.audit('mapping',id,dict(raw=raw,confirmed=a,snapshot_id=s.id)); return dict(snapshot_id=s.id,task=t)

    @app.get('/api/sources')
    def sources(snapshot_id:str):
        s=store.snapshot(snapshot_id); records=store.all('import')
        return [dict(id=source,count=sum(t.source==source for t in s.tasks),state='Imported file' if any(r['source']==source and r['committed'] and store.snapshot(r['snapshot_id']).corridor==s.corridor for r in records) else 'Sample data',last_import=max([r['created_at'] for r in records if r['source']==source and r['committed'] and store.snapshot(r['snapshot_id']).corridor==s.corridor],default=s.created_at)) for source in SOURCES]

    @app.get('/api/samples/{source}')
    def sample(source:str,format:str='csv'):
        if source not in SOURCES or format not in ['csv','json']: raise ValueError('Unknown source or format')
        path=Path(__file__).resolve().parents[2]/'sample_data'/f'{source}.{format}'
        return Response(path.read_text(encoding='utf-8'),media_type='application/json' if format=='json' else 'text/csv',headers={'Content-Disposition':f'attachment; filename="{source}-illustrative.{format}"'})

    @app.post('/api/benchmarks')
    def benchmarks(body:GenerateRequest):
        s=store.snapshot(body.snapshot_id); require_current(s)
        return enqueue('benchmark',lambda:benchmark(s,body.horizon,body.day))

    @app.get('/api/benchmarks/{id}')
    def benchmark_result(id:str): return store.get(id,'benchmark')

    @app.get('/api/benchmarks/{id}/export')
    def benchmark_export(id:str,format:str='json'):
        data=store.get(id,'benchmark')
        if format not in ['csv','json']: raise ValueError('Choose JSON or CSV')
        return Response(safe_csv(data['rows']) if format=='csv' else json.dumps(data,indent=2),media_type='text/csv' if format=='csv' else 'application/json',headers={'Content-Disposition':f'attachment; filename="benchmark-{id}.{format}"'})

    @app.get('/api/plans/{id}/export')
    def export(id:str,format:str='json'):
        p=plan_view(store.get(id,'plan')); s=store.snapshot(p['snapshot_id'])
        if format not in ['csv','json']: raise ValueError('Choose JSON or CSV')
        task_index={t.id:t for t in s.tasks}
        rows=[dict(plan_id=id,snapshot_id=s.id,anchor_utc=s.anchor,**a,title=task_index[a['task_id']].title) for a in p['assignments']]
        return Response(safe_csv(rows) if format=='csv' else json.dumps(dict(plan=p,snapshot=s.model_dump()),indent=2),media_type='text/csv' if format=='csv' else 'application/json',headers={'Content-Disposition':f'attachment; filename="railblox-{id}.{format}"'})

    from .intelligence_api import router as intelligence_router
    intelligence_api=intelligence_router(store,enqueue,mutation_lock,require_current,locks_for,source_head)
    app.include_router(intelligence_api)
    from .platform_api import platform_router, Automation
    automation=Automation(store,mutation_lock,intelligence_api.services,settings)
    app.state.automation=automation
    app.include_router(platform_router(store,mutation_lock,intelligence_api.services,automation))
    return app


app=create_app()
