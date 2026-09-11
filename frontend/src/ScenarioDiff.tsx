import {ArrowDownRight, ArrowRight, Clock3, MapPin} from 'lucide-react';
import type {Scenario, Task} from './types';
import {time} from './api';

function IntervalList({value, anchor}: {value: unknown; anchor: string}) {
  if (!Array.isArray(value)) return <p className="muted">No existing record</p>;
  return <div className="diff-intervals">{value.map((entry, index) => {
    const item = Array.isArray(entry) ? {start:entry[0],end:entry[1],section:''} : entry as {start:number;end:number;section?:string};
    return <div key={index}>{item.section && <span className="diff-section"><MapPin size={13}/>{item.section}</span>}<span className="diff-times">{time(item.start,anchor,true)}<ArrowRight size={13}/>{time(item.end,anchor,true)}</span></div>;
  })}</div>;
}

export function ScenarioDiff({change, anchor}: {change: Scenario['change']; anchor: string}) {
  if (change.kind === 'shorten') {
    const before = change.before as {start:number;end:number};
    const after = change.after as {start:number;end:number};
    return <div className="scenario-window-diff">
      <div className="window-diff-card"><span className="section-overline">ORIGINAL WINDOW</span><strong>{before.end-before.start}<small>minutes</small></strong><p><Clock3 size={14}/>{time(before.start,anchor)} — {time(before.end,anchor)} IST</p><span className="window-capacity"/></div>
      <div className="window-diff-direction"><ArrowRight size={22}/><span>−{before.end-after.end}m</span></div>
      <div className="window-diff-card modified"><span className="section-overline">SCENARIO WINDOW</span><strong>{after.end-after.start}<small>minutes</small></strong><p><Clock3 size={14}/>{time(after.start,anchor)} — {time(after.end,anchor)} IST</p><div className="window-capacity"><span style={{width:`${(after.end-after.start)/(before.end-before.start)*100}%`}}/></div></div>
    </div>;
  }
  if (change.kind === 'crew' || change.kind === 'freight') return <div className="before-after"><section className="input-change"><h3>Before <span>Baseline</span></h3><IntervalList value={change.before} anchor={anchor}/></section><section className="input-change modified"><h3>After <span>Scenario</span></h3><IntervalList value={change.after} anchor={anchor}/></section></div>;
  const task=change.after as Task;
  return <div className="scenario-task-diff"><span className="diff-task-icon"><ArrowDownRight size={22}/></span><div><span className="section-overline">SCENARIO TASK</span><h3>{task.title}</h3><div className="scenario-task-facts"><span>{task.id}</span><span>{task.duration} min work</span><span>{task.section}</span><span>Due {time(task.due,anchor,true)} IST</span><span>{task.verified?'Verified asset':'Mapping unresolved'}</span></div></div></div>;
}
