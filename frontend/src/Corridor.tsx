import {useState, type KeyboardEvent} from 'react';
import {ArrowRight, CircleDot, X} from 'lucide-react';
import type {Snapshot, Plan} from './types';

export function Corridor({snapshot, plan, selected, onSection}: {snapshot: Snapshot; plan: Plan; selected?: string; onSection: (s: string) => void}) {
  const [isolation, setIsolation] = useState(false);
  const [table, setTable] = useState(false);
  const sections = snapshot.sections.filter(s => s.line === 'UP');
  const stations = [sections[0]?.origin, ...sections.map(s => s.destination)];
  const width = Math.max(680, stations.length * 125);
  const left = 58;
  const step = (width - 116) / Math.max(1, stations.length - 1);
  const assigned = new Set(plan.assignments.map(a => a.task_id));
  const activate = (event: KeyboardEvent<SVGGElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSection(id); }
  };

  return <section className="corridor-panel" aria-label="Corridor and protection">
    <div className="corridor-heading"><div><span className="section-overline">NETWORK OVERVIEW</span><h2>Corridor & protection</h2></div><span className="network-id">{snapshot.corridor === 'small' ? 'CR / 01' : 'CR / 02'}</span></div>
    <div className="corridor-controls"><span><span className="map-key"/>Directed network</span><label className="switch-label"><input type="checkbox" checked={isolation} onChange={e => setIsolation(e.target.checked)}/><span className="switch-track"/>Isolation overlays</label></div>
    {table ? <div className="table-scroll dark-table"><table><thead><tr><th>Section</th><th>Stations</th><th>Chainage (m)</th><th>Isolation</th></tr></thead><tbody>{snapshot.sections.map(s => <tr key={s.id}><td><button className="text-button" onClick={() => onSection(s.id)}>{s.id}</button></td><td>{s.line === 'UP' ? `${s.origin} → ${s.destination}` : `${s.destination} → ${s.origin}`}</td><td>{s.chainage_start}–{s.chainage_end}</td><td>{s.isolation}</td></tr>)}</tbody></table></div> : <div className="diagram-scroll" tabIndex={0} aria-label="Directed corridor diagram">
      <svg viewBox={`0 0 ${width} 204`} width={width} aria-label="Synthetic stations and directed adjacent sections" role="group">
        {sections.map((s, i) => {
          const a = left + i * step;
          const b = a + step;
          const downId = s.id.replace('UP', 'DN');
          const upTasks = snapshot.tasks.filter(t => t.section === s.id && assigned.has(t.id));
          const downTasks = snapshot.tasks.filter(t => t.section === downId && assigned.has(t.id));
          return <g key={s.id}>
            {isolation && <g><rect x={a+7} y="62" width={step-14} height="108" rx="8" fill="#2ead9a" fillOpacity=".10" stroke="#499388" strokeDasharray="3 4"/><text x={(a+b)/2} y="158" textAnchor="middle" className="map-isolation">{s.isolation}</text></g>}
            {[{id:s.id,y:91,tasks:upTasks,up:true},{id:downId,y:121,tasks:downTasks,up:false}].map(line => <g key={line.id} role="button" tabIndex={0} aria-label={`Select section ${line.id}`} onClick={() => onSection(line.id)} onKeyDown={e => activate(e,line.id)} className="map-section">
              <rect x={a+8} y={line.y-13} width={step-16} height="26" fill="transparent"/>
              <line x1={a+6} x2={b-6} y1={line.y} y2={line.y} stroke={selected===line.id?'var(--gold)':line.tasks.length?'#c2d0d7':'#56616a'} strokeWidth={selected===line.id?4:2.5}/>
              <path d={line.up?`M ${b-25} ${line.y-4} l 5 4 -5 4`:`M ${a+25} ${line.y-4} l -5 4 5 4`} fill="none" stroke={selected===line.id?'var(--gold)':'#b3c2c9'} strokeWidth="1.5"/>
              <text x={(a+b)/2} y={line.up?77:143} textAnchor="middle" className="map-section-id">{line.id}</text>
            </g>)}
            {!!upTasks.length && <g><rect x={(a+b)/2-27} y="30" width="54" height="22" rx="5" fill="#ffffff" fillOpacity=".08" stroke="#ffffff" strokeOpacity=".12"/><text x={(a+b)/2} y="45" textAnchor="middle" className="map-task-count">{upTasks.length} {upTasks.length===1?'task':'tasks'}</text><path d={`M ${(a+b)/2} 53 V 64`} stroke="#727e86" strokeDasharray="2 2"/></g>}
          </g>;
        })}
        {stations.map((station,i) => <g key={station}>
          <text x={left+i*step} y="24" textAnchor="middle" className="station-code">{station}</text>
          <rect x={left+i*step-8} y="82" width="16" height="48" rx="8" fill="#20282e" stroke="#7d8a91" strokeWidth="1.2"/>
          <circle cx={left+i*step} cy="91" r="4" fill="#e8edef"/><circle cx={left+i*step} cy="121" r="4" fill="#e8edef"/>
          <text x={left+i*step} y="183" textAnchor="middle" className="map-chainage">{((i===0?sections[0]?.chainage_start:sections[i-1]?.chainage_end)||0).toLocaleString()} m</text>
        </g>)}
      </svg>
    </div>}
    <div className="corridor-footer"><span><CircleDot size={13}/>{stations.length} stations<span className="footer-dot">·</span>{snapshot.sections.length} directed sections</span><button onClick={() => setTable(!table)}>{table?'View diagram':'Section table'}<ArrowRight size={13}/></button></div>
    {selected && <div className="map-selection"><span>Selected <strong>{selected}</strong></span><button onClick={() => onSection(selected)}>Clear selection <X size={12}/></button></div>}
  </section>;
}
