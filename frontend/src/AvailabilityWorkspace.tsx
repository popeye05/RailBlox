import {AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, Clock3, ShieldAlert} from 'lucide-react';
import {useQuery} from '@tanstack/react-query';
import {NavLink} from 'react-router-dom';
import {api} from './api';
import {Badge, Panel} from './components';
import type {Plan, Snapshot} from './types';

type Estimate = {
  asset_id: string; asset_type: string; section: string; criticality: string;
  operational_state: string; confidence: string; source: string; source_record_id: string;
  source_timestamp: string; model_version: string; horizon_hours: number;
  failure_probability: number; planned_failure_probability: number;
  expected_downtime_hours: number; planned_downtime_hours: number;
  baseline_availability: number; planned_availability: number;
  downtime_avoided_hours: number; net_uptime_gain_hours: number;
  scheduled_task_ids: string[]; scheduled_block_ids: string[]; uncertainty: string;
};
type Summary = {
  snapshot_id: string; plan_id: string|null; horizon_days: number; day: number;
  model_version: string; as_of: string; synthetic: boolean; estimates: Estimate[];
  metrics: {assets:number;critical_assets:number;critical_improved:number;baseline_availability:number|null;planned_availability:number|null;downtime_avoided_hours:number;planned_downtime_hours:number;net_uptime_gain_hours:number;overdue_critical:number};
  data_quality: {low_confidence_assets:string[];missing_health_assets:string[];stale_sources:string[];block_new_recommendation:boolean};
  disclaimer: string;
};

const pct=(value:number|null)=>value===null?'—':`${(value*100).toFixed(2)}%`;
const hours=(value:number)=>`${value.toFixed(2)} h`;
const tone=(value:string)=>value==='critical'?'bad':value==='high'?'warn':'neutral';

export function AvailabilityWorkspace({snapshot,plan,horizon,day}:{snapshot:Snapshot;plan:Plan;horizon:7|30;day:number}){
  const query=useQuery({queryKey:['availability',snapshot.id,plan.id,horizon,day],queryFn:()=>api<Summary>(`/api/availability/summary?snapshot_id=${encodeURIComponent(snapshot.id)}&plan_id=${encodeURIComponent(plan.id)}&horizon=${horizon}&day=${day}`)});
  if(query.isLoading)return <div className="loading"><span className="spinner"/>Loading asset availability evidence…</div>;
  if(query.error)return <div className="error" role="alert"><AlertTriangle size={18}/><div><strong>Availability evidence unavailable</strong><p>{query.error.message}</p><button onClick={()=>query.refetch()}>Retry availability</button></div></div>;
  const data=query.data!;const m=data.metrics;
  const sorted=[...data.estimates].sort((a,b)=>a.planned_availability-b.planned_availability);
  return <div className="availability-workspace">
    <div className="availability-hero"><div><span className="section-overline">ASSET UPTIME MAXIMIZATION</span><h2>Know what the plan protects</h2><p>Compare expected asset availability before and after this proposal, then review the evidence behind every change.</p></div><Badge tone="warn">Synthetic advisory</Badge></div>
    {data.data_quality.block_new_recommendation&&<div className="warning availability-warning"><ShieldAlert size={18}/><div><strong>Officer review required before approval</strong><p>{data.data_quality.low_confidence_assets.length} critical/high asset records have review-required confidence. The estimate is visible for planning, but this state should block a new recommendation until the source is confirmed.</p><NavLink className="text-button" to="/operations">Review source conditions <ArrowUpRight size={14}/></NavLink></div></div>}
    <div className="metrics availability-metrics">
      <div className="metric"><span className="metric-label">Assets assessed <CheckCircle2 size={15}/></span><strong>{m.assets}</strong><small>{m.critical_assets} critical assets</small></div>
      <div className="metric"><span className="metric-label">Baseline availability <Clock3 size={15}/></span><strong>{pct(m.baseline_availability)}</strong><small>Expected downtime only</small></div>
      <div className="metric"><span className="metric-label">Planned availability <ArrowUpRight size={15}/></span><strong>{pct(m.planned_availability)}</strong><small>{m.critical_improved} critical assets improved</small></div>
      <div className={'metric '+(m.net_uptime_gain_hours>=0?'metric-good':'')}><span className="metric-label">Net uptime gain <ArrowDownRight size={15}/></span><strong>{m.net_uptime_gain_hours>=0?'+':''}{hours(m.net_uptime_gain_hours)}</strong><small>{hours(m.downtime_avoided_hours)} avoided · {hours(m.planned_downtime_hours)} planned</small></div>
    </div>
    <div className="availability-grid">
      <Panel title="Asset availability by criticality" aside={<Badge>{data.estimates.length} records</Badge>}>
        <div className="table-scroll"><table className="availability-table"><thead><tr><th>Asset / state</th><th>Criticality</th><th>Before</th><th>After plan</th><th>Trade-off</th><th>Review evidence</th></tr></thead><tbody>{sorted.map(row=><tr key={row.asset_id}>
          <td><strong>{row.asset_id}</strong><small>{row.asset_type} · {row.section} · {row.operational_state}</small></td>
          <td><Badge tone={tone(row.criticality)}>{row.criticality}</Badge></td>
          <td>{pct(row.baseline_availability)}<small>{hours(row.expected_downtime_hours)} expected downtime</small></td>
          <td>{pct(row.planned_availability)}<small>{row.scheduled_task_ids.length?row.scheduled_task_ids.join(', '):'No scheduled work'}</small></td>
          <td><strong className={row.net_uptime_gain_hours>=0?'positive':'negative'}>{row.net_uptime_gain_hours>=0?'+':''}{hours(row.net_uptime_gain_hours)}</strong><small>{hours(row.downtime_avoided_hours)} avoided</small></td>
          <td><small>{row.source} / {row.source_record_id}</small><small>{row.confidence==='review_required'?'Review required':row.confidence}</small></td>
        </tr>)}</tbody></table></div>
        {!sorted.length&&<p className="empty">No asset-health records are available in this snapshot.</p>}
      </Panel>
      <div className="availability-side">
        <Panel title="Officer decision guide"><div className="padded"><div className="guide-item"><span>1</span><div><strong>Check the source</strong><p>Confirm the SMMS record, timestamp, condition and confidence for critical assets.</p></div></div><div className="guide-item"><span>2</span><div><strong>Read the trade-off</strong><p>Downtime avoided is expected failure downtime; planned downtime is possession and restoration time.</p></div></div><div className="guide-item"><span>3</span><div><strong>Validate before approval</strong><p>Safety, timetable, isolation and resource constraints remain hard rules outside this estimate.</p></div></div></div></Panel>
        <Panel title="Data quality" aside={<Badge tone={data.data_quality.block_new_recommendation?'warn':'good'}>{data.data_quality.block_new_recommendation?'Review':'Ready'}</Badge>}><div className="padded quality-list"><p><strong>{data.data_quality.low_confidence_assets.length}</strong> review-required health records</p><p><strong>{data.data_quality.missing_health_assets.length}</strong> assets without health data</p><p><strong>{m.overdue_critical}</strong> overdue critical assets</p><small>Evidence timestamp: {new Date(data.as_of).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST</small><small>Model: {data.model_version}</small></div></Panel>
      </div>
    </div>
    <p className="availability-footnote">{data.disclaimer} Source timestamps and uncertainty travel with the estimate. Shortening or changing a block requires a new plan calculation.</p>
  </div>;
}
