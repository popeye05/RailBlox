from uuid import uuid4
from .domain import Task, utcnow


def scenario_snapshot(snapshot, request):
    s=snapshot.model_copy(deep=True); s.id=str(uuid4()); s.parent_id=snapshot.id; s.created_at=utcnow()
    change=request.model_dump()
    if request.kind=='shorten':
        w=next((w for w in s.windows if w.id==request.target),None)
        if not w: raise ValueError('Unknown window')
        if w.end-request.minutes<=w.start: raise ValueError('Shortening must leave a positive window')
        change.update(before=dict(start=w.start,end=w.end),after=dict(start=w.start,end=w.end-request.minutes)); w.end-=request.minutes
    elif request.kind=='freight':
        m=next((m for m in s.movements if m['id']==request.target and m['kind']=='Freight'),None)
        if not m: raise ValueError('Select a freight movement')
        change['before']=[dict(o) for o in m['occupancies']]
        for o in m['occupancies']: o['start']+=request.minutes; o['end']+=request.minutes
        change['after']=m['occupancies']
    elif request.kind=='crew':
        r=next((r for r in s.resources if r.id==request.target),None)
        if not r or request.end<=request.start: raise ValueError('Select a resource and a positive interval')
        change['before']=r.availability; availability=[]
        for a,b in r.availability:
            if a<min(b,request.start): availability.append([a,min(b,request.start)])
            if max(a,request.end)<b: availability.append([max(a,request.end),b])
        r.availability=availability; change['after']=availability
    elif request.kind=='urgent':
        a=next((a for a in s.assets if a['section']==request.target),None)
        if not a: raise ValueError('Select a canonical section')
        t=Task(id='URG-'+s.id[:8],department='ENG',asset_id=a['id'],section=a['section'],line=a['line'],chainage_m=a['chainage_m'],isolation=a['isolation'],title='Scenario urgent inspection',duration=request.duration,mandatory=True,priority='Critical',earliest=request.start,due=request.deadline,resources=[next(r.id for r in s.resources if r.id.startswith('ENG'))],weight=100,source_record_id='scenario-'+s.id)
        s.tasks.append(t); change['after']=t.model_dump()
    else:
        t=s.tasks[0]
        if request.kind=='impossible': t.due=1; t.mandatory=True
        else:
            t=next((t for t in s.tasks if not t.verified),t); t.verified=False; t.mandatory=True
        change['after']=t.model_dump()
    s.scenario=change
    return s
