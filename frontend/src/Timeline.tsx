import {useId, useState, type KeyboardEvent, type ReactNode} from 'react';
import {ArrowRight, List, ShieldCheck, TrainFront} from 'lucide-react';
import {Panel} from './components';
import type {Snapshot, Plan, Task, Package} from './types';
import {time, date} from './api';

const colors = {'ENG':'#3a6fbb','TRD':'#188b7e','S&T':'#8062b0'};

export function Timeline({snapshot, plan, day, onTask, onPackage, section='', department='', priority='', status='', compact=false}: {snapshot:Snapshot;plan:Plan;day:number;onTask:(t:Task)=>void;onPackage:(p:Package)=>void;section?:string;department?:string;priority?:string;status?:string;compact?:boolean}) {
  const [table,setTable]=useState(false);
  const [showTrains,setShowTrains]=useState(true);
  const pattern=useId().replaceAll(':','');
  const tasks=new Map(snapshot.tasks.map(task=>[task.id,task]));
  const packages=plan.packages.filter(p=>Math.floor(p.start/1440)===day&&(!section||p.sections.includes(section))&&status!=='unscheduled'&&p.task_ids.some(id=>(!department||tasks.get(id)?.department===department)&&(!priority||tasks.get(id)?.priority===priority)));
  const holds=(snapshot.protected_intervals||[]).filter(r=>r.start<(day+1)*1440&&r.end>day*1440&&(!section||r.section===section));
  const dailyMovements=snapshot.movements.flatMap(m=>m.occupancies.filter(o=>o.start<(day+1)*1440&&o.end>day*1440));
  const start=Math.max(day*1440,Math.floor(Math.min(day*1440+60,...packages.map(p=>p.start),...holds.map(r=>r.start),...dailyMovements.map(r=>r.start))/60)*60);
  const end=Math.min((day+1)*1440,Math.ceil(Math.max(day*1440+900,...packages.map(p=>p.end),...holds.map(r=>r.end),...dailyMovements.map(r=>r.end))/60)*60);
  const tickStep=Math.ceil((end-start)/840)*60;
  const labelWidth=250;
  const chartWidth=870;
  const width=1160;
  const x=(minute:number)=>labelWidth+(minute-start)/(end-start)*chartWidth;
  let currentY=48;
  const rows:ReactNode[]=[];
  const activation=(event:KeyboardEvent<SVGGElement>,callback:()=>void)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();callback();}};

  for(const pack of packages){
    const y=currentY;
    rows.push(<g key={pack.id} role="button" tabIndex={0} aria-label={`${pack.id} on timeline`} onClick={()=>onPackage(pack)} onKeyDown={event=>activation(event,()=>onPackage(pack))} className="timeline-interactive">
      <rect x="0" y={y} width={width} height="54" fill="#f7f8f9"/>
      <path d={`M 17 ${y+20} l 4 4 -4 4`} stroke="#66717b" fill="none" strokeWidth="1.5"/>
      <text x="34" y={y+22} className="timeline-package-name">{pack.id}</text><text x="34" y={y+41} className="timeline-label-secondary">{pack.sections.join(', ')} · {pack.task_ids.length} tasks</text>
      <rect x={x(pack.start)} y={y+16} width={Math.max(6,x(pack.end)-x(pack.start))} height="23" rx="5" fill="#323d46"/>
      <rect x={x(pack.start)+1} y={y+17} width={Math.max(2,x(pack.preparation_end)-x(pack.start)-1)} height="21" fill={`url(#stage-${pattern})`}/>
      <rect x={x(pack.restoration_start)} y={y+17} width={Math.max(2,x(pack.end)-x(pack.restoration_start)-1)} height="21" fill={`url(#stage-${pattern})`}/>
      <text x={x(pack.end)+10} y={y+32} className="timeline-margin">{pack.end-pack.start}m closure <tspan fill="#657a70">· {pack.margin}m margin</tspan></text>
    </g>);
    currentY+=54;
    for(const id of pack.task_ids){
      const task=tasks.get(id)!;
      if((department&&task.department!==department)||(priority&&task.priority!==priority))continue;
      const assignment=plan.assignments.find(a=>a.task_id===id)!;
      const ty=currentY;
      const color=colors[task.department];
      rows.push(<g key={id} role="button" tabIndex={0} aria-label={`${id} ${task.title} on timeline`} onClick={()=>onTask(task)} onKeyDown={event=>activation(event,()=>onTask(task))} className="timeline-interactive">
        <rect width={width} y={ty} height="48" fill="#fff"/>
        <line x1="0" x2={width} y1={ty+48} y2={ty+48} stroke="#f0f1f3"/>
        <circle cx="20" cy={ty+19} r="3.5" fill={color}/><text x="33" y={ty+23} className="timeline-task-name">{task.id} <tspan fill="#76818a" fontWeight="400">/ {task.department}</tspan></text>
        <text x="33" y={ty+40} className="timeline-label-secondary">{task.title.length>27?task.title.slice(0,26)+'…':task.title}</text>
        <rect x={x(assignment.start)} y={ty+12} width={Math.max(5,x(assignment.end)-x(assignment.start))} height="25" rx="5" fill={color} fillOpacity=".14" stroke={color} strokeOpacity=".30"/>
        <rect x={x(assignment.start)} y={ty+16} width="3" height="17" rx="1.5" fill={color}/>
        <text x={x(assignment.end)+9} y={ty+29} className="timeline-work-duration" fill={color}>{task.duration}m</text>
        <title>{task.title} · {time(assignment.start,snapshot.anchor)}–{time(assignment.end,snapshot.anchor)} IST</title>
      </g>);
      currentY+=48;
    }
  }
  const movements=snapshot.movements.flatMap(m=>m.occupancies.filter(o=>o.start>=start&&o.start<end&&(!section||o.section===section)).map(o=>({...o,id:m.id,kind:m.kind,margin:m.margin})));
  if(showTrains&&movements.length){
    rows.push(<g key="train-heading"><rect y={currentY} width={width} height="34" fill="#f9fafb"/><text x="17" y={currentY+22} className="timeline-group-label">PROTECTED TRAIN OCCUPANCY</text></g>);
    currentY+=34;
    for(const sectionId of [...new Set(movements.map(m=>m.section))]){
      const y=currentY;
      rows.push(<g key={'movement-'+sectionId}><rect width={width} y={y} height="36" fill="#fff"/><text x="33" y={y+23} className="timeline-label-secondary">{sectionId}</text>{movements.filter(m=>m.section===sectionId).map(m=><g key={m.id+m.start}><rect x={x(m.start-m.margin)} y={y+8} width={Math.max(5,x(m.end+m.margin)-x(m.start-m.margin))} height="20" rx="3" fill={`url(#train-${pattern})`} stroke="#b5a389"/><title>{m.id} · {m.kind} · {time(m.start,snapshot.anchor)}–{time(m.end,snapshot.anchor)} + {m.margin} min protection margin</title></g>)}</g>);
      currentY+=36;
    }
  }
  if(holds.length){
    rows.push(<g key="holds-heading"><rect y={currentY} width={width} height="34" fill="#faf5f2"/><text x="17" y={currentY+22} className="timeline-group-label">EXISTING BLOCKS / PLANNING HOLDS</text></g>);
    currentY+=34;
    for(const hold of holds){
      const y=currentY;
      rows.push(<g key={'hold-'+hold.id+hold.kind}><text x="17" y={y+22} className="timeline-label-secondary">{hold.id} · {hold.section}</text><rect x={x(Math.max(start,hold.start))} y={y+7} width={Math.max(3,x(Math.min(end,hold.end))-x(Math.max(start,hold.start)))} height="20" rx="2" fill="#ead4ce" stroke="#ac6556"/><title>{hold.kind} · {time(hold.start,snapshot.anchor)}–{time(hold.end,snapshot.anchor)}</title></g>);
      currentY+=35;
    }
  }
  const height=Math.max(currentY+14,180);

  return <Panel className="timeline-panel" title={compact?'Schedule comparison':date(day*1440,snapshot.anchor)} aside={<div className="timeline-options"><label className="check"><input type="checkbox" checked={showTrains} onChange={e=>setShowTrains(e.target.checked)}/>Train occupancy</label><button className="table-toggle" onClick={()=>setTable(!table)}><List size={14}/>{table?'Show timeline':'Table alternative'}</button></div>}>
    <div className="legend"><span className="eng">Engineering</span><span className="trd">Traction</span><span className="signal">Signal & Telecom</span><span className="stage">Preparation / restoration</span><span className="train">Protected movement</span></div>
    {table?<div className="table-scroll"><table><thead><tr><th>Task / package</th><th>Section</th><th>Start IST</th><th>End IST</th><th>Margin</th></tr></thead><tbody>{packages.map(pack=><tr key={pack.id}><td><button className="text-button" onClick={()=>onPackage(pack)}>{pack.id}</button></td><td>{pack.sections.join(', ')}</td><td>{time(pack.start,snapshot.anchor)}</td><td>{time(pack.end,snapshot.anchor)}</td><td>{pack.margin} min</td></tr>)}{plan.assignments.filter(a=>packages.some(p=>p.window_id===a.window_id)).map(a=><tr key={a.task_id}><td><button className="text-button" onClick={()=>onTask(tasks.get(a.task_id)!)}>{a.task_id}</button></td><td>{tasks.get(a.task_id)?.section}</td><td>{time(a.start,snapshot.anchor)}</td><td>{time(a.end,snapshot.anchor)}</td><td>—</td></tr>)}{showTrains&&movements.map(m=><tr key={m.id+m.section+m.start}><td>{m.id}<small>Protected movement</small></td><td>{m.section}</td><td>{time(m.start-m.margin,snapshot.anchor)}</td><td>{time(m.end+m.margin,snapshot.anchor)}</td><td>{m.margin} min protection</td></tr>)}{holds.map(h=><tr key={h.kind+h.id}><td>{h.id}<small>{h.kind}</small></td><td>{h.section}</td><td>{time(h.start,snapshot.anchor)}</td><td>{time(h.end,snapshot.anchor)}</td><td>Work excluded</td></tr>)}</tbody></table></div>:<div className="timeline-scroll" tabIndex={0} aria-label="Schedule timeline in Asia/Kolkata; scroll horizontally">
      <svg width={width} height={height} role="group" aria-label="Maintenance closures and protected train occupancy in minutes">
        <defs><pattern id={`stage-${pattern}`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line y2="5" stroke="#f0f4f6" strokeOpacity=".45" strokeWidth="2"/></pattern><pattern id={`train-${pattern}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><rect width="6" height="6" fill="#f7f2e9"/><line y2="6" stroke="#c4b49b" strokeWidth="1.5"/></pattern></defs>
        {rows}<rect y="0" width={width} height="48" fill="#fff"/><text x="17" y="29" className="timeline-group-label">PACKAGE / TASK</text>
        {Array.from({length:Math.floor((end-start)/tickStep)+1},(_,i)=>start+i*tickStep).map(minute=><g key={minute}><line x1={x(minute)} x2={x(minute)} y1="48" y2={height} stroke="#4c5d70" strokeOpacity=".075" pointerEvents="none"/><text x={x(minute)} y="29" textAnchor="middle" className="axis-label">{time(minute,snapshot.anchor)}</text></g>)}
        <line x1={labelWidth-12} x2={labelWidth-12} y1="0" y2={height} stroke="#e7eaed"/>
        <line x1={x(day*1440+120)} x2={x(day*1440+120)} y1="41" y2={height} stroke="#e14f46" strokeWidth="1.2" strokeDasharray="3 4" pointerEvents="none"/><circle cx={x(day*1440+120)} cy="43" r="3" fill="#e14f46"/>
      </svg>
    </div>}
    {!packages.length&&<p className="empty">No packages match this day and these filters. Select another day or reset filters.</p>}
    <div className="timeline-selectors">{packages.map(pack=><div key={pack.id}><button onClick={()=>onPackage(pack)} className="package-button">{pack.id}<ArrowRight size={14}/></button>{pack.task_ids.filter(id=>!department||tasks.get(id)?.department===department).map(id=><button key={id} onClick={()=>onTask(tasks.get(id)!)} className={'task-chip '+tasks.get(id)?.department.replace('&','')}>{id} · {tasks.get(id)?.title}</button>)}</div>)}</div>
    <footer className="panel-foot"><span><ShieldCheck size={14}/>Modeled protection intervals</span><span><TrainFront size={14}/>Asia/Kolkata · Simulation time 02:00</span></footer>
  </Panel>;
}
