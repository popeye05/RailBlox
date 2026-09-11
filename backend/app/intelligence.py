"""Local, explainable statistical and rule baselines for SPEC 2.

No trained operational risk model or external LLM is implied. All evidence IDs,
sample sizes, scoring weights and limitations travel with the recommendation.
"""
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from uuid import uuid4
from .domain import utcnow
from .intelligence_models import Evidence, Factors, History
from .footprints import incompatibility

WEIGHTS = {'safety': 25, 'security': 10, 'operational': 20, 'criticality': 15,
           'time_sensitivity': 15, 'restrictions': 10, 'combining': 5}
LABELS = {'safety': 'Safety impact', 'security': 'Security of the defect',
          'operational': 'Operational impact', 'criticality': 'Criticality',
          'time_sensitivity': 'Time sensitivity', 'restrictions': 'Existing failures / restrictions',
          'combining': 'Possibility of combining work'}


def intersects(a, b, c, d):
    return a < d and c < b


def seed_evidence(snapshot):
    anchor = datetime.fromisoformat(snapshot.anchor)
    history = []
    # Explicitly fabricated completed outcomes, not copies of planned durations.
    seen = set()
    for task in snapshot.tasks:
        key = (task.section, task.department, task.work_class)
        if key in seen:
            continue
        seen.add(key)
        for i, ratio in enumerate([1, 1.05, 1.1, 1.15, 1.25, 1.4]):
            weather = 'rain' if i >= 4 else 'clear'
            cause = {'ENG': 'track defect', 'TRD': 'OHE fault', 'S&T': 'signal failure'}[task.department]
            history.append(dict(id=f'H-{len(history)+1:04}', section=task.section,
                                department=task.department, work_class=task.work_class,
                                planned_minutes=task.duration, actual_minutes=math.ceil(task.duration * ratio),
                                delay_minutes=max(0, math.ceil(task.duration * (ratio-1))),
                                completed_at=(anchor-timedelta(days=20-i)).isoformat(), weather=weather,
                                narrative=f'Repeated {cause} near {task.section}; work completed in {math.ceil(task.duration*ratio)} minutes. Weather: {weather}.'))
    section = next((s['id'] for s in snapshot.sections if s['line']=='UP'),snapshot.sections[0]['id'])
    other = next((s['id'] for s in snapshot.sections if s['line'] == 'DN'), section)
    assessments = {t.id: dict(safety=5 if t.mandatory else 2, security=None,
                             operational=4 if t.mandatory else 2, criticality=5 if t.priority=='Critical' else 3,
                             time_sensitivity=4 if t.due<1440 else 2, restrictions=3 if t.mandatory else 1,
                             combining=3 if sum(u.section==t.section for u in snapshot.tasks)>1 else 0)
                   for t in snapshot.tasks}
    return Evidence.model_validate(dict(id=str(uuid4()), snapshot_id=snapshot.id,
        division=f'DEMO-{snapshot.corridor.upper()}', synthetic=True, as_of=anchor.isoformat(),
        assessments=assessments, history=history,
        feeds=[dict(source=source, received_at=anchor.isoformat(), max_age_minutes=120)
               for source in ['COA', 'ROAMS', 'MIS/PAM', 'Weather']],
        blocks=[dict(id='COA-B1', section=other, start=220, end=260, status='planned',
                     reason='Synthetic existing block reservation')],
        cautions=[dict(id='COA-C1', section=section, start=0, end=1440, speed_kph=30,
                       description='Synthetic temporary speed restriction; review access arrangements')],
        weather=[dict(id='WX-01', section=section, start=195, end=270, condition='heavy rain',
                      planning_hold=True, reason='Demonstration policy: no planned work during this supplied hold interval')]))


def validate_references(evidence, snapshot):
    sections = {s['id'] for s in snapshot.sections}
    tasks = {t.id for t in snapshot.tasks}
    if evidence.snapshot_id != snapshot.id:
        raise ValueError('Evidence belongs to another snapshot')
    if set(evidence.assessments) - tasks:
        raise ValueError('Assessment references an unknown task')
    if any(r.section not in sections for rows in [evidence.blocks, evidence.cautions, evidence.weather, evidence.history] for r in rows):
        raise ValueError('Evidence references an unknown directed section')


def freshness(evidence, now=None):
    # Synthetic demonstrations use their explicitly displayed clock, never pretend live.
    clock = evidence.as_of if evidence.synthetic else (now or datetime.now(timezone.utc))
    records = []
    for source in ['COA', 'ROAMS', 'MIS/PAM', 'Weather']:
        feed = next((f for f in evidence.feeds if f.source == source), None)
        age = (clock-feed.received_at).total_seconds()/60 if feed else None
        state = 'missing' if not feed else 'unavailable' if feed.state=='unavailable' else 'future timestamp' if age < -5 else 'stale' if age > feed.max_age_minutes else 'available'
        records.append(dict(source=source, state=state, age_minutes=round(age, 1) if age is not None else None,
                            received_at=feed.received_at.isoformat() if feed else None))
    return records


def quantile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q*len(ordered))-1)]


def duration_estimate(task, history, condition=None):
    cohort = [h for h in history if h.department==task.department and h.work_class==task.work_class]
    local = [h for h in cohort if h.section==task.section]
    if len(local) >= 3:
        cohort = local
    weather_matches = [h for h in cohort if h.weather==condition]
    weather_conditioned = bool(condition and len(weather_matches)>=3)
    if weather_conditioned:
        cohort = weather_matches
    if len(cohort) < 3:
        return dict(planned=task.duration, low=task.duration, expected=task.duration, high=None,
                    planning_minutes=task.duration, samples=len(cohort), evidence_ids=[h.id for h in cohort],
                    confidence='Insufficient history', method='Engineering estimate; no statistical range',
                    extension_rate=None, weather_conditioned=False)
    ratios = [h.actual_minutes/h.planned_minutes for h in cohort]
    low = math.ceil(task.duration*quantile(ratios, .2))
    expected = math.ceil(task.duration*median(ratios))
    high = math.ceil(task.duration*quantile(ratios, .8))
    return dict(planned=task.duration, low=low, expected=expected, high=high,
                planning_minutes=max(task.duration, high), samples=len(cohort), evidence_ids=[h.id for h in cohort],
                confidence='Limited evidence' if len(cohort)<20 else 'Historical sample; uncalibrated',
                method='Matched actual/planned ratios; empirical P20–P80 range, P80 planning allowance',
                extension_rate=round(sum(h.actual_minutes>h.planned_minutes for h in cohort)/len(cohort),3),
                weather_conditioned=weather_conditioned)


def priority(task, evidence):
    assessment = evidence.assessments.get(task.id, Factors()).model_dump()
    factors = [dict(key=k, label=LABELS[k], value=assessment[k], weight=w,
                    contribution=round(assessment[k]/5*w, 1) if assessment[k] is not None else None)
               for k,w in WEIGHTS.items()]
    lower = round(sum(f['contribution'] or 0 for f in factors),1)
    upper = round(lower+sum(f['weight'] for f in factors if f['value'] is None),1)
    incomplete = any(f['value'] is None for f in factors)
    level = 'High' if task.mandatory or lower>=65 else 'Medium' if lower>=35 else 'Low'
    return dict(score=lower if not incomplete else None, score_low=lower, score_high=upper,
                level=level, factors=factors, missing=[f['label'] for f in factors if f['value'] is None],
                method='Explicit weighted policy, not a learned safety-risk probability',
                reasons=(['Mandatory work remains a hard requirement'] if task.mandatory else [])+
                        [f"{f['label']}: {f['value']}/5" for f in factors if f['value'] is not None and f['value']>=4])


CAUSES = [('Signalling', 'signal failure', r'\b(?:signal failure|signal fault|track circuit)\b'),
          ('Traction', 'OHE fault', r'\b(?:ohe fault|overhead|catenary|power failure)\b'),
          ('Engineering', 'track defect', r'\b(?:track defect|broken rail|rail fracture|turnout)\b'),
          ('Weather', 'weather disruption', r'\b(?:flood(?:ing)?|heavy rain|storm|poor visibility)\b'),
          ('Resources', 'resource delay', r'\b(?:crew unavailable|resource delay|equipment failure|material shortage)\b')]


def extract_text(text, sections, history=()):
    matches = []
    for category, cause, pattern in CAUSES:
        for match in re.finditer(pattern, text, re.I):
            prefix = text[max(0, match.start()-35):match.start()]
            negated = bool(re.search(r'\b(?:no|not|without|ruled out)\b[^.;,]*$', prefix, re.I))
            matches.append(dict(category=category, cause=cause, text=match.group(),
                                start=match.start(), end=match.end(), negated=negated))
    locations = [s for s in sections if re.search(r'(?<![\w-])'+re.escape(s)+r'(?![\w-])',text,re.I)]
    times = [dict(text=m.group(), minutes=int(m.group(1))*(60 if m.group(2).lower().startswith('h') else 1))
             for m in re.finditer(r'\b(\d{1,3})\s*(hours?|hrs?|minutes?|mins?)\b',text,re.I)]
    affirmed = {m['cause'] for m in matches if not m['negated']}
    recurring = [h.id for h in history if h.section in locations and any(c in h.narrative.lower() for c in affirmed)]
    return dict(original=text, method='Local vocabulary and span extraction; officer verification required',
                matches=matches, locations=locations, durations=times, recurring_evidence=recurring,
                severity='Not inferred', operational_impact='Requires officer confirmation',
                uncertainty='No supported cause found' if not affirmed else 'Keyword evidence; not causal proof')


def intelligence_rows(snapshot, evidence, outcomes=()):
    history_by_id = {h.id:h for h in evidence.history}
    history_by_id.update({o['history']['id']:History.model_validate(o['history']) for o in outcomes})
    history = list(history_by_id.values())
    rows = []
    for task in snapshot.tasks:
        estimate = duration_estimate(task, history)
        peers = [h for h in history if h.section==task.section and h.department==task.department]
        dependencies = []
        for predecessor in task.predecessors:
            dependencies.append(dict(kind='Sequential', record=predecessor, detail='Must complete before this work'))
        for other in snapshot.tasks:
            if other.id==task.id:
                continue
            if set(task.resources)&set(other.resources):
                dependencies.append(dict(kind='Resource', record=other.id, detail='Shared '+', '.join(sorted(set(task.resources)&set(other.resources)))))
            if task.section==other.section and (task.work_class in other.incompatible or other.work_class in task.incompatible):
                dependencies.append(dict(kind='Incompatible work', record=other.id, detail='Cannot share one possession'))
        potential = [u.id for u in snapshot.tasks if u.id!=task.id and u.section==task.section
                     and task.work_class not in u.incompatible and u.work_class not in task.incompatible and u.ready and u.verified]
        windows = []
        for w in snapshot.windows:
            if task.section not in w.sections:
                continue
            conflicts = []
            for m in snapshot.movements:
                if any(o['section'] in w.sections and intersects(w.start,w.end,o['start']-m.get('margin',0),o['end']+m.get('margin',0)) for o in m['occupancies']):
                    conflicts.append(dict(kind='Train occupancy', record=m['id']))
            for b in evidence.blocks:
                if b.status not in ['completed','cancelled'] and b.section in w.sections and intersects(w.start,w.end,b.start,b.end):
                    conflicts.append(dict(kind='Existing block',record=b.id))
            weather = [r.model_dump() for r in evidence.weather if r.section in w.sections and intersects(w.start,w.end,r.start,r.end)]
            cautions = [r.model_dump() for r in evidence.cautions if r.section in w.sections and intersects(w.start,w.end,r.start,r.end)]
            windows.append(dict(id=w.id, start=w.start, end=w.end, eligibility_issue=incompatibility(task,w,snapshot),
                                conflicts=conflicts, weather=weather, cautions=cautions))
        risks = []
        if not task.verified: risks.append('Unresolved asset location')
        if not task.ready: risks.append('Materials not ready')
        if estimate['high'] is None: risks.append('Insufficient duration history')
        if any(x['weather'] for x in windows): risks.append('Weather exposure in candidate windows')
        if any(x['cautions'] for x in windows): risks.append('Caution order review required')
        ranking = priority(task,evidence)
        if ranking['missing']: risks.append('Incomplete priority assessment')
        rows.append(dict(task_id=task.id,title=task.title,section=task.section,department=task.department,
                         mandatory=task.mandatory, source=task.source, source_record_id=task.source_record_id,
                         earliest=task.earliest, due=task.due, priority=ranking, duration=estimate, dependencies=dependencies,
                         combination_candidates=potential, windows=windows, risks=risks,
                         risk_level='Review required' if risks else 'No flagged input issues',
                         action='Resolve location / readiness' if not task.verified or not task.ready else 'Review feasible recommendation',
                         history=dict(count=len(peers), average_actual=round(mean(h.actual_minutes for h in peers),1) if peers else None,
                                      extensions=sum(h.actual_minutes>h.planned_minutes for h in peers), evidence_ids=[h.id for h in peers])))
    return sorted(rows,key=lambda r:(not r['mandatory'],-r['priority']['score_low'],r['due'],r['task_id']))


def alerts(evidence, outcomes=()):
    result = [dict(id='feed-'+f['source'],level='Review',kind='Data freshness',record=f['source'],
                   message=f"{f['source']} is {f['state']}; new recommendations are blocked.")
              for f in freshness(evidence) if f['state']!='available']
    for h in evidence.history:
        if h.actual_minutes>h.planned_minutes*1.5:
            result.append(dict(id='extension-'+h.id,level='Review',kind='Duration extension',record=h.id,
                               message=f'Actual {h.actual_minutes} min exceeds planned {h.planned_minutes} min by {round((h.actual_minutes/h.planned_minutes-1)*100)}%.'))
    counts=Counter(h.section for h in evidence.history if any(m['category']!='Weather' and not m['negated'] for m in extract_text(h.narrative,[])['matches']))
    for section,count in counts.items():
        if count>=3:
            result.append(dict(id='repeat-'+section,level='Review',kind='Repeated incidents',record=section,
                               message=f'{count} historical records mention a failure/defect on this section. Keyword baseline; inspect source records.'))
    for o in outcomes:
        h=o['history']; predicted=o['predicted_high']
        if predicted and h['actual_minutes']>predicted:
            result.append(dict(id='outcome-'+o['id'],level='Review',kind='Prediction exceeded',record=o['task_id'],
                               message=f"Recorded {h['actual_minutes']} min exceeds the saved upper estimate of {predicted} min."))
    return result


def intelligence_brief(snapshot, evidence, rows, outcomes=()):
    """Create a concise, explainable local intelligence brief for the workspace.

    This is deliberately deterministic: it gives the prototype an assistant-like
    experience without pretending that a remote model has assessed safety or
    operational authority. Every signal is derived from the supplied evidence.
    """
    open_issues = sum(bool(r['risks']) for r in rows)
    high_priority = sum(r['priority']['level'] == 'High' for r in rows)
    mandatory = sum(r['mandatory'] for r in rows)
    history = {h.id: h for h in evidence.history}
    for outcome in outcomes:
        h = History.model_validate(outcome['history'])
        if h.completed_at <= evidence.as_of:
            history[h.id] = h
    extensions = sum(h.actual_minutes > h.planned_minutes for h in history.values())
    fresh = freshness(evidence)
    stale = [f['source'] for f in fresh if f['state'] != 'available']
    current_alerts = alerts(evidence, outcomes)

    section_counts = Counter()
    for alert in current_alerts:
        if alert['kind'] == 'Repeated incidents':
            section_counts[alert['record']] += 1
    top_section = section_counts.most_common(1)[0][0] if section_counts else None

    signals = []
    if stale:
        signals.append(dict(kind='Data quality', tone='warning', title='Evidence needs refresh',
                            detail=f"{', '.join(stale)} require review before a new recommendation can be generated."))
    else:
        signals.append(dict(kind='Data quality', tone='positive', title='Evidence is current',
                            detail=f'{len(fresh)} source feeds are within their configured freshness windows.'))
    if high_priority:
        signals.append(dict(kind='Priority', tone='attention', title=f'{high_priority} high-priority work items',
                            detail=f'{mandatory} mandatory requirement(s) remain protected by the planning policy.'))
    if extensions:
        detail = f'{extensions} historical outcome(s) exceeded their planned duration.'
        if top_section:
            detail += f' Review the repeated signal around {top_section}.'
        signals.append(dict(kind='Pattern', tone='attention', title='Duration pattern detected', detail=detail))
    if not signals:
        signals.append(dict(kind='Status', tone='positive', title='No review signals detected',
                            detail='The current evidence has no configured baseline alerts.'))

    if stale:
        narrative = 'New recommendations require refreshed source evidence.'
    elif open_issues:
        narrative = f'{open_issues} of {len(rows)} work items have review signals; inspect the evidence before approval.'
    else:
        narrative = f'The evidence supports a planning pass across {len(rows)} work items.'
    return dict(
        narrative=narrative,
        signals=signals[:4],
        metrics=dict(work_items=len(rows), high_priority=high_priority,
                     mandatory=mandatory, review_items=open_issues,
                     alerts=len(current_alerts), historical_outcomes=len(history)),
        basis=dict(method='Deterministic local rules and historical evidence',
                   source_feeds=len(fresh), source_records=len(history),
                   generated_at=utcnow()),
        limitation='Advisory pattern detection; it is not a safety case, risk probability or operational instruction.'
    )


def planning_snapshot(snapshot, evidence, rows):
    result=snapshot.model_copy(deep=True)
    result.id=str(uuid4()); result.parent_id=snapshot.id
    result.scenario=dict(kind='intelligence', evidence_id=evidence.id)
    lookup={r['task_id']:r for r in rows}
    for task in result.tasks:
        if lookup[task.id]['duration']['planning_minutes']>1440:
            raise ValueError(f'Duration estimate for {task.id} exceeds the supported 1440-minute task limit; engineering review required')
        task.duration=lookup[task.id]['duration']['planning_minutes']
        # Missing factors use the disclosed lower bound, never silently imputed values.
        task.weight=max(1,round(lookup[task.id]['priority']['score_low']*10))
    restrictions=[]
    for kind, records in [('Existing block',evidence.blocks),('Weather hold',evidence.weather),('Caution hold',evidence.cautions)]:
        for r in records:
            applies=(kind=='Existing block' and r.status not in ['completed','cancelled']) if kind=='Existing block' else r.planning_hold if kind=='Weather hold' else r.work_prohibited
            if applies:
                restrictions.append(dict(id=r.id,section=r.section,start=r.start,end=r.end,kind=kind))
    result.protected_intervals = result.protected_intervals + restrictions
    return result


def duration_diagnostics(history):
    """Chronological holdout; a result is only illustrative for synthetic history."""
    from types import SimpleNamespace
    ordered=sorted(history,key=lambda h:(h.completed_at,h.id))
    split=max(1,int(len(ordered)*.7)); train=ordered[:split]; test=ordered[split:]
    errors=[]; covered=[]
    for h in test:
        estimate=duration_estimate(SimpleNamespace(department=h.department,work_class=h.work_class,section=h.section,duration=h.planned_minutes),train)
        if estimate['high'] is not None:
            errors.append(abs(h.actual_minutes-estimate['expected']))
            covered.append(estimate['low']<=h.actual_minutes<=estimate['high'])
    return dict(method='First 70% by completion time trains ratio baseline; final 30% held out',
                training_records=len(train),test_records=len(test),evaluated=len(errors),
                mean_absolute_error=round(mean(errors),2) if errors else None,
                interval_coverage=round(mean(covered),3) if covered else None,
                limitation='Synthetic evaluation does not establish operational accuracy or calibrated confidence.')
