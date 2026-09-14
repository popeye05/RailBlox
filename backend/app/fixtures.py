import random
from .domain import Task, Window, Resource, Snapshot


def acceptance():
    sections = [dict(id=f'S{i}-{line}', origin=['ARV','BEL','CHN'][i-1], destination=['BEL','CHN','DVR'][i-1], line=line, chainage_start=(i-1)*10000, chainage_end=i*10000, isolation=f'ISO-{i}') for i in range(1,4) for line in ['UP','DN']]
    assets = [_asset(s, i) for i, s in enumerate(sections)]
    def task(id, dept, duration, section='S1-UP', **kw):
        asset=next(a for a in assets if a['section']==section)
        return Task(id=id, department=dept, asset_id=asset['id'], section=section, chainage_m=asset['chainage_m'], title=kw.pop('title',f'{dept} inspection {id}'), duration=duration, earliest=0, due=210, resources=[f'{dept}-1'], source_record_id=id, isolation=['ISO-'+section[1]], **kw)
    tasks=[task('A','ENG',40,mandatory=True,priority='Critical',weight=100,title='Track geometry correction',work_class='track'),
           task('B','TRD',25,title='Overhead equipment inspection',access=['traffic','electrical'],weight=30),
           task('C','S&T',15,title='Detection testing after track work',predecessors=['A'],weight=20),
           task('D','ENG',30,'S3-UP',mandatory=True,priority='High',title='Independent turnout inspection'),
           task('E','S&T',30,title='Conflicting track circuit intervention',work_class='circuit',incompatible=['track']),
           task('F','ENG',50,title='Shared engineering crew renewal'),
           task('G','TRD',20,verified=False,title='Unverified mast location',remarks='Between Bel / Bell east; asset alias needs confirmation.'),
           task('H','S&T',25,'S2-UP',title='Signal equipment verification'),
           task('I','TRD',30,'S2-UP',ready=False,title='Materials pending: bonding inspection'),
           task('J','ENG',20,'S2-UP',title='Upcoming rail inspection')]
    tasks[3].earliest=300; tasks[3].due=390
    tasks[7].due=600; tasks[8].due=600; tasks[9].earliest=1440; tasks[9].due=1800
    windows=[Window(id='W1',start=120,end=210,sections=['S1-UP'],isolation=['ISO-1']),Window(id='W2',start=300,end=390,sections=['S3-UP'],isolation=['ISO-3']),Window(id='W3',start=480,end=570,sections=['S2-UP'],isolation=['ISO-2']),Window(id='W4',start=1560,end=1650,sections=['S2-UP'],isolation=['ISO-2'])]
    resources=[Resource(id=f'{d}-1',setup=5) for d in ['ENG','TRD','S&T']]
    movements=[dict(id='FRT-01',kind='Freight',direction='UP',forecast='2026-09-09T12:00:00+00:00',margin=5,occupancies=[dict(section='S1-UP',start=90,end=105),dict(section='S2-UP',start=110,end=125),dict(section='S3-UP',start=130,end=145)]),dict(id='PAX-01',kind='Passenger',direction='DN',forecast='2026-09-09T12:00:00+00:00',margin=5,occupancies=[dict(section='S3-DN',start=130,end=145),dict(section='S2-DN',start=150,end=165),dict(section='S1-DN',start=170,end=185)])]
    return Snapshot(id='small-v1',corridor='small',name='Aravalli demonstration corridor',tasks=tasks,windows=windows,resources=resources,sections=sections,assets=assets,movements=movements)


def presentation():
    rng=random.Random(42)
    stations=['NVA','KDR','MLR','PNR','SVR','TLP','UDR','VNA']
    sections=[dict(id=f'P{i}-{line}',origin=stations[i-1],destination=stations[i],line=line,chainage_start=(i-1)*12000,chainage_end=i*12000,isolation=f'PISO-{i}') for i in range(1,8) for line in ['UP','DN']]
    assets=[_asset(s, i, chainage_offset=4000) for i, s in enumerate(sections)]
    resources=[Resource(id=f'{d}-{i}',setup=5) for d in ['ENG','TRD','S&T'] for i in range(1,4)]
    windows=[]; tasks=[]; movements=[]
    for day in range(30):
        for j in range(4):
            s=sections[(day*4+j)%14]; start=day*1440+120+j*180
            windows.append(Window(id=f'PW-{day:02}-{j}',start=start,end=start+120,sections=[s['id']],isolation=[s['isolation']]))
            if j<3 or day%3==0:
                dept=['ENG','TRD','S&T'][len(tasks)%3]; a=next(a for a in assets if a['section']==s['id'])
                tasks.append(Task(id=f'PM-{len(tasks)+1:03}',department=dept,asset_id=a['id'],section=s['id'],line=s['line'],chainage_m=a['chainage_m'],title=['Rail and fastening inspection','OHE condition inspection','Signal apparatus testing'][['ENG','TRD','S&T'].index(dept)],duration=rng.choice([25,30,40,45]),mandatory=len(tasks)%5==0,earliest=max(0,start-60),due=start+120,weight=rng.randint(10,50),priority='High' if len(tasks)%5==0 else 'Normal',resources=[f'{dept}-{j%3+1}'],isolation=a['isolation'],access=['traffic','electrical'] if dept=='TRD' else ['traffic'],verified=len(tasks)%19!=18,source_record_id=f'P-{len(tasks)}',source=['TMS','TDMS','SMMS'][['ENG','TRD','S&T'].index(dept)]))
        for direction in ['UP','DN']:
            ordered=[s for s in sections if s['line']==direction]
            if direction=='DN': ordered.reverse()
            movements.append(dict(id=f'PF-{day}-{direction}',kind='Freight',direction=direction,margin=5,forecast='2026-09-09T12:00:00+00:00',occupancies=[dict(section=s['id'],start=day*1440+1000+i*20,end=day*1440+1010+i*20) for i,s in enumerate(ordered)]))
    for t in tasks:
        if t.mandatory: t.verified=True
    tasks[-1].due=-1; tasks[-1].earliest=0; tasks[-1].mandatory=False
    return Snapshot(id='presentation-v1',corridor='presentation',name='Navira–Vayana synthetic corridor',tasks=tasks,windows=windows,resources=resources,sections=sections,assets=assets,movements=movements)


def _asset(section, index, chainage_offset=2500):
    """Synthetic asset-health fixture; values are deliberately reviewable."""
    critical = index % 7 in (0, 1)
    degraded = index % 4 in (0, 3)
    return dict(
        id=f'AS-{section["id"]}', section=section['id'], line=section['line'],
        chainage_m=section['chainage_start'] + chainage_offset,
        isolation=[section['isolation']], verified=True,
        health=dict(
            asset_type='track' if index % 3 == 0 else 'ohe' if index % 3 == 1 else 'signal',
            section=section['id'], chainage_m=section['chainage_start'] + chainage_offset,
            criticality='critical' if critical else 'high' if index % 2 else 'normal',
            service_impact=5 if critical else 3 if degraded else 2,
            operational_state='degraded' if degraded else 'healthy',
            last_inspection_at='2026-09-10T08:00:00+05:30',
            maintenance_due_at='2026-09-12T00:00:00+05:30' if critical else '2026-10-01T00:00:00+05:30',
            failure_count_12m=3 if degraded else 1,
            exposure_hours_12m=8760,
            estimated_repair_hours=4 if critical else 3,
            source='SMMS', source_record_id=f'SMMS-{index+1:03}',
            source_timestamp='2026-09-10T08:05:00+05:30',
            confidence='review_required' if critical else 'medium',
        ),
    )
