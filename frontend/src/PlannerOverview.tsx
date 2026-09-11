import {ArrowRight, Check} from 'lucide-react';
import {NavLink, useSearchParams} from 'react-router-dom';
import type {Package, Plan, Snapshot} from './types';
import {time} from './api';

export function PlannerOverview({plan, snapshot, onPackage}: {plan: Plan; snapshot: Snapshot; onPackage: (p: Package) => void}) {
  const [params] = useSearchParams();
  return (
    <section className="plan-overview" aria-label="Proposal overview">
      <div className="overview-heading"><span className="section-overline">SELECTED PROPOSAL</span><span className="version-tag">{plan.id.slice(0,8)}</span></div>
      <div className="overview-summary"><div><strong>{plan.packages.length} work packages</strong><p>{plan.metrics.scheduled} tasks across {new Set(plan.packages.flatMap(p => p.sections)).size} directed sections</p></div></div>
      <div className="overview-check">{plan.validation.valid && <Check size={15}/>}<span>{plan.validation.valid ? 'Modeled constraints checked' : 'Review modeled conflicts'}</span></div>
      <div className="overview-packages">
        {plan.packages.slice(0,2).map(p => <button key={p.id} onClick={() => onPackage(p)}><div><strong>{p.id}</strong><small>{p.sections.join(', ')} · {time(p.start,snapshot.anchor)} IST</small></div><span>{p.margin}m<small>margin</small></span><ArrowRight size={15}/></button>)}
        {!plan.packages.length && <p>No feasible packages in this proposal.</p>}
      </div>
      <div className="overview-bottom"><span>{plan.runtime_seconds.toFixed(2)}s solve</span><NavLink to={{pathname:'/opportunities',search:params.toString()}}>Explore additions <ArrowRight size={14}/></NavLink></div>
    </section>
  );
}
