import {useEffect, useRef, useState, type ReactNode} from 'react';
import {NavLink, useLocation, useSearchParams} from 'react-router-dom';
import {Activity, BarChart3, BookOpen, CalendarDays, ChevronRight, ClipboardList, Database, FileText, GitBranch, Layers, Lightbulb, Menu, ShieldCheck, TrainFront, Wrench, X} from 'lucide-react';
import {useIdentity} from './Auth';
import type {Context, Snapshot} from './types';

const logo = new URL('../assets0/logo.png', import.meta.url).href;
const groups = [
  {label:'OPERATIONS',links:[
    {path:'/queue',label:'Block queue',icon:ClipboardList},
    {path:'/planner',label:'Planner',icon:CalendarDays},
    {path:'/traffic',label:'Train movements',icon:TrainFront},
    {path:'/operations',label:'Operations',icon:Activity},
  ]},
  {label:'MAINTENANCE',links:[
    {path:'/tasks',label:'Maintenance',icon:Wrench},
    {path:'/availability',label:'Availability',icon:Layers},
    {path:'/opportunities',label:'Opportunities',icon:Lightbulb},
    {path:'/disruptions',label:'Disruption lab',icon:GitBranch},
  ]},
  {label:'EVIDENCE & REPORTS',links:[
    {path:'/data',label:'Data review',icon:Database},
    {path:'/insights',label:'Insights',icon:Activity},
    {path:'/reports',label:'Reporting',icon:FileText},
    {path:'/benchmarks',label:'Results',icon:BarChart3},
  ]},
];

export function WorkspaceShell({children,context,corridorId,onCorridor,snapshot}:{children:ReactNode;context?:Context;corridorId:string;onCorridor:(id:string)=>void;snapshot?:Snapshot}) {
  const location=useLocation(),[params]=useSearchParams(),identity=useIdentity();
  const [menuOpen,setMenuOpen]=useState(false);
  const toggle=useRef<HTMLButtonElement>(null),navigation=useRef<HTMLElement>(null);
  const page=[...groups.flatMap(g=>g.links),{path:'/profile',label:'Your profile'},{path:'/admin/users',label:'User access'},{path:'/help',label:'Workspace guide'}].find(l=>l.path===location.pathname);
  useEffect(()=>{document.title=`${page?.label||'Workspace'} · RailBLOX`;setMenuOpen(false)},[location.pathname,page?.label]);
  useEffect(()=>{if(menuOpen)navigation.current?.querySelector<HTMLAnchorElement>('a')?.focus()},[menuOpen]);
  const initials=(identity.name||identity.email||'Demo').split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase();
  return <div className="app railway-site">
    <a className="skip-link" href="#workspace-content">Skip to workspace</a>
    <aside className={`workspace-rail ${menuOpen?'is-open':''}`} onKeyDown={e=>{if(e.key==='Escape'){setMenuOpen(false);toggle.current?.focus()}}}>
      <NavLink className="workspace-brand" to={{pathname:'/queue',search:params.toString()}} aria-label="RaILBLOX home"><span><img src={logo} alt="RaILBLOX"/></span><small>MAINTENANCE COORDINATION</small></NavLink>
      <nav ref={navigation} id="primary-navigation" aria-label="Main navigation">{groups.map(group=><div className="workspace-nav-group" key={group.label}><span>{group.label}</span>{group.links.map(({path,label,icon:Icon})=><NavLink key={path} to={{pathname:path,search:params.toString()}} onClick={()=>setMenuOpen(false)}><Icon size={17}/><span>{label}</span><ChevronRight className="nav-indicator" size={14}/></NavLink>)}</div>)}</nav>
      <div className="workspace-rail-bottom"><NavLink to="/help"><BookOpen size={17}/>Workspace guide</NavLink>{identity.role==='admin'&&<NavLink to="/admin/users"><ShieldCheck size={17}/>User access</NavLink>}<div className="environment-label"><i/>Planning prototype<small>Synthetic / imported snapshots</small></div></div>
    </aside>
    <div className="main-column">
      <header className="workspace-topbar">
        <button ref={toggle} className="mobile-menu-toggle" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X size={20}/>:<Menu size={20}/>}<span>{menuOpen?'Close':'Menu'}</span></button>
        <NavLink className="mobile-brand" to="/queue" aria-label="RaILBLOX home"><img src={logo} alt="RaILBLOX"/></NavLink>
        <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14}/><strong>{page?.label||'Planner'}</strong></div>
        <label className="network-picker"><span>PLANNING NETWORK</span><select aria-label="Corridor" value={context?.corridors.some(c=>c.id===corridorId)?corridorId:''} disabled={!context?.corridors.length} onChange={e=>onCorridor(e.target.value)}>{!context?.corridors.length&&<option value="">{context?'No corridors provisioned':'Loading networks…'}</option>}{context?.corridors.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <NavLink className="account-profile" to="/profile"><span className="account-initials" aria-hidden="true">{initials}</span><span><strong>{identity.name||'Your account'}</strong><small>Profile & security</small></span></NavLink>
      </header>
      {children}
      <footer className="workspace-bottom"><span>RailBLOX <span>·</span> {identity.division} workspace</span><span>{snapshot?`${snapshot.sections.length} directed sections · `:''}Asia/Kolkata · IST</span></footer>
    </div>
  </div>;
}
