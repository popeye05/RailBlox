from .footprints import incompatibility, eligible


def overlap(a,b,c,d): return a<d and c<b


def validate(snapshot, plan, locks=None):
    violations=[]
    def fail(rule, records, message, interval=None):
        violations.append(dict(rule_id='SYNTHETIC-'+rule,records=records,message=message,interval=interval))
    ts={t.id:t for t in snapshot.tasks}; ws={w.id:w for w in snapshot.windows}; rs={r.id:r for r in snapshot.resources}
    assignments=plan.get('assignments',[]); packages=plan.get('packages',[]); seen={}; ps={p['window_id']:p for p in packages}
    for p in packages:
        w=ws.get(p['window_id'])
        if not w: fail('WINDOW',[p['window_id']],'Unknown window'); continue
        if p['start']<max(w.start,plan['day']*1440) or p['end']>min(w.end,(plan['day']+plan['horizon'])*1440): fail('WINDOW',[w.id],'Package outside window/horizon',[p['start'],p['end']])
        if set(p['sections'])!=set(w.sections): fail('FOOTPRINT',[w.id],'Closure footprint differs from source window')
        work=[a for a in assignments if a['window_id']==w.id]
        if not work: fail('STAGES',[w.id],'Empty package'); continue
        if p.get('preparation_end')!=p['start']+w.preparation or p.get('restoration_start')!=p['end']-w.restoration or min(a['start'] for a in work)<p['start']+w.preparation or max(a['end'] for a in work)>p['end']-w.restoration:
            fail('STAGES',[w.id],'Preparation/restoration missing or work exceeds stages')
        for movement in snapshot.movements:
            for o in movement['occupancies']:
                margin=movement.get('margin',0)
                if o['section'] in w.sections and overlap(p['start'],p['end'],o['start']-margin,o['end']+margin): fail('TRAIN',[w.id,movement['id']],'Closure overlaps protected train occupancy',[o['start']-margin,o['end']+margin])
        for r in snapshot.protected_intervals:
            if r['section'] in w.sections and overlap(p['start'],p['end'],r['start'],r['end']):
                fail('PROTECTION',[w.id,r['id']],f"Closure overlaps {r['kind']}",[r['start'],r['end']])
    for a in assignments:
        t=ts.get(a['task_id']); w=ws.get(a['window_id'])
        if not t or not w: fail('REFERENCE',[a['task_id']],'Unknown task/window'); continue
        if t.id in seen: fail('ONCE',[t.id],'Task assigned more than once')
        seen[t.id]=a
        reason=incompatibility(t,w,snapshot)
        if reason: fail('FOOTPRINT',[t.id,w.id],reason)
        if a['end']-a['start']!=t.duration: fail('DURATION',[t.id],'Work duration changed')
        if a['start']<max(t.earliest,plan['day']*1440) or a['end']>min(t.due,(plan['day']+plan['horizon'])*1440): fail('DEADLINE',[t.id],'Work outside eligibility/deadline')
        if w.id not in ps: fail('STAGES',[t.id],'Assignment has no closure package')
        for r_id in t.resources:
            r=rs.get(r_id)
            if not r or not any(lo<=a['start'] and a['end']+r.setup<=hi for lo,hi in r.availability): fail('CALENDAR',[t.id,r_id],'Resource unavailable including setup/travel')
    for t in eligible(snapshot,plan['day'],plan['horizon']):
        if (t.mandatory or t.started) and t.id not in seen: fail('MANDATORY',[t.id],'Required or started work unscheduled'+(' / unresolved asset' if not t.verified else ''))
    for a in assignments:
        t=ts.get(a['task_id'])
        if not t: continue
        for predecessor in t.predecessors:
            if predecessor not in seen or seen[predecessor]['end']>a['start']: fail('DEPENDENCY',[t.id,predecessor],'Predecessor missing or not finished')
    for i,a in enumerate(assignments):
        ta=ts.get(a['task_id'])
        if not ta: continue
        for b in assignments[i+1:]:
            tb=ts.get(b['task_id'])
            if not tb: continue
            if a['window_id']==b['window_id'] and (ta.work_class in tb.incompatible or tb.work_class in ta.incompatible): fail('INCOMPATIBLE',[ta.id,tb.id],'Incompatible work classes in same possession')
    for r in snapshot.resources:
        points=[]
        for a in assignments:
            if a['task_id'] in ts and r.id in ts[a['task_id']].resources:
                points.extend([(a['start'],1,a['task_id']),(a['end']+r.setup,-1,a['task_id'])])
        use=0
        for minute,delta,tid in sorted(points):
            use+=delta
            if use>r.capacity: fail('CAPACITY',[r.id,tid],'Resource capacity exceeded including setup/travel',[minute,minute+1])
    for i,p in enumerate(packages):
        for q in packages[i+1:]:
            if set(p['sections'])&set(q['sections']) and overlap(p['start'],p['end'],q['start'],q['end']): fail('CLOSURE',[p['window_id'],q['window_id']],'Separate possessions overlap')
    for tid,a in (locks or {}).items():
        if tid not in seen or any(seen[tid][k]!=a[k] for k in ['start','end','window_id']): fail('LOCK',[tid],'Locked or started commitment changed')
    return dict(valid=not violations,label='Passed modeled checks' if not violations else 'Modeled conflicts found',violations=violations)
