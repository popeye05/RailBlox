def union_minutes(intervals):
    end=None; total=0
    for a,b in sorted(intervals):
        if end is None or a>=end: total+=b-a; end=b
        elif b>end: total+=b-end; end=b
    return total


def metrics(snapshot, plan, baseline=None):
    from .footprints import eligible
    tasks=eligible(snapshot,plan['day'],plan['horizon']); assigned=plan['assignments']; ids={a['task_id'] for a in assigned}
    sections={s for p in plan['packages'] for s in p['sections']}
    cost=sum(union_minutes([(p['start'],p['end']) for p in plan['packages'] if s in p['sections']]) for s in sections)
    old={a['task_id']:a for a in (baseline or {}).get('assignments',[])}; new={a['task_id']:a for a in assigned}
    changed=[k for k,a in old.items() if k not in new or (a['start'],a['window_id'])!=(new[k]['start'],new[k]['window_id'])]
    return dict(scheduled=len(ids),eligible=len(tasks),mandatory_met=sum(t.mandatory and t.id in ids for t in tasks),mandatory_required=sum(t.mandatory for t in tasks),optional_scheduled=sum(not t.mandatory and t.id in ids for t in tasks),service=sum(t.weight for t in tasks if t.id in ids),closed_section_minutes=cost,unresolved=sum(not t.verified for t in tasks),changed_assignments=len(changed),changed_task_ids=changed,start_shift=sum(abs(a['start']-new[k]['start']) for k,a in old.items() if k in new),new_tasks=[k for k in new if k not in old])
