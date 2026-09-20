import {useEffect, useRef, useState, type ReactNode} from 'react';
import {NavLink, useLocation, useSearchParams} from 'react-router-dom';
import {ChevronRight, Menu, X} from 'lucide-react';
import {LogoutButton} from './LogoutButton';
import {useIdentity} from './Auth';
import type {Context} from './types';

const logo = new URL('../assets0/logo.png', import.meta.url).href;
const operations = [
  {path:'/queue',label:'Block queue'},
  {path:'/planner',label:'Planner'},
  {path:'/traffic',label:'Train movements'},
  {path:'/operations',label:'Operations'},
];
const groups = [
  {label:'Maintenance planning',links:[
    {path:'/tasks',label:'Maintenance'},
    {path:'/opportunities',label:'Opportunities'},
    {path:'/disruptions',label:'Disruption lab'},
  ]},
  {label:'Predictive decision support',links:[
    {path:'/availability',label:'Availability'},
    {path:'/insights',label:'Insights'},
  ]},
  {label:'Evidence & reports',links:[
    {path:'/data',label:'Data review'},
    {path:'/reports',label:'Reporting'},
    {path:'/benchmarks',label:'Results'},
  ]},
];

export function WorkspaceShell({children,context,corridorId,onCorridor}:{children:ReactNode;context?:Context;corridorId:string;onCorridor:(id:string)=>void}) {
  const location=useLocation(),[params]=useSearchParams(),identity=useIdentity();
  const [menuOpen,setMenuOpen]=useState(false);
  const toggle=useRef<HTMLButtonElement>(null),navigation=useRef<HTMLElement>(null);
  const page=[...operations,...groups.flatMap(g=>g.links),{path:'/profile',label:'Your profile'},{path:'/admin/users',label:'User access'},{path:'/help',label:'Workspace guide'},{path:'/help/methods',label:'Model & planning basis'}].find(l=>l.path===location.pathname);
  useEffect(()=>{document.title=`${page?.label||'Workspace'} · RailBLOX`;setMenuOpen(false)},[location.pathname,page?.label]);
  useEffect(()=>{if(menuOpen)navigation.current?.querySelector<HTMLAnchorElement>('a')?.focus()},[menuOpen]);
  const initials=(identity.name||identity.email||'Demo').split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase();
  const destination=(pathname:string)=>({pathname,search:params.toString()});
  const closeMenu=()=>{setMenuOpen(false);toggle.current?.focus()};
  return <div className="app railway-site">
    <a className="skip-link" href="#workspace-content">Skip to workspace</a>
    <header className="site-header">
      <div className="workspace-masthead">
        <NavLink className="masthead-brand" to={destination('/queue')} aria-label="RailBLOX home">
          <span className="masthead-logo"><img src={logo} alt="RailBLOX" width="860" height="264"/></span>
          <span className="brand-purpose">Railway maintenance planning</span>
        </NavLink>
        <label className="network-picker"><span>Planning network</span><select aria-label="Corridor" value={context?.corridors.some(c=>c.id===corridorId)?corridorId:''} disabled={!context?.corridors.length} onChange={e=>onCorridor(e.target.value)}>{!context?.corridors.length&&<option value="">{context?'No corridors provisioned':'Loading networks…'}</option>}{context?.corridors.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <NavLink className="account-profile" to={destination('/profile')}><span className="account-initials" aria-hidden="true">{initials}</span><span><strong>{identity.name||'Your account'}</strong><small>Profile & security</small></span></NavLink>
        <LogoutButton/>
      </div>
      <div className="operations-band">
        <nav className="operations-navigation" aria-label="Operations navigation">{operations.map(({path,label})=><NavLink key={path} to={destination(path)} onClick={()=>setMenuOpen(false)}>{label}</NavLink>)}</nav>
      </div>
    </header>
    <div className="workspace-location">
      <button ref={toggle} className="mobile-menu-toggle" aria-expanded={menuOpen} aria-controls="support-navigation" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X size={17}/>:<Menu size={17}/>}<span>{menuOpen?'Close':'Menu'}</span></button>
      <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} aria-hidden="true"/><strong>{page?.label||'Planner'}</strong></div>
    </div>
    <div className="workspace-body">
      <aside className={`workspace-rail ${menuOpen?'is-open':''}`} onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();closeMenu()}}}>
        <nav ref={navigation} id="support-navigation" aria-label="Supporting navigation">
          {groups.map(group=><div className="workspace-nav-group" key={group.label}><span>{group.label}</span>{group.links.map(({path,label})=><NavLink key={path} to={destination(path)} onClick={()=>{if(menuOpen)closeMenu()}}>{label}</NavLink>)}</div>)}
          <div className="workspace-nav-group"><span>Workspace</span><NavLink to={destination('/help')} onClick={()=>{if(menuOpen)closeMenu()}}>Workspace guide</NavLink>{identity.role==='admin'&&<NavLink to={destination('/admin/users')} onClick={()=>{if(menuOpen)closeMenu()}}>User access</NavLink>}</div>
        </nav>
        <div className="environment-label">Data sources<small>Synthetic / imported snapshots</small></div>
      </aside>
      <div className="main-column">
        {['/planner','/queue','/tasks','/opportunities','/disruptions','/availability','/insights'].includes(location.pathname)&&<section className="workflow-context" aria-label="Workflow purpose"><div><strong>{['/availability','/insights'].includes(location.pathname)?'Predictive decision support':'Maintenance block planning'}</strong><p>{['/availability','/insights'].includes(location.pathname)?'Assess modeled risk, expected availability and evidence confidence. Estimates inform a proposal; they do not authorize track access.':'Schedule work into protected track-closure windows, resolve resource conflicts and submit a proposal for officer review.'}</p></div><NavLink to={destination('/help/methods')}>How the models work</NavLink></section>}
        {children}
        <footer className="workspace-bottom"><span>RailBLOX</span><span>Maintenance coordination</span></footer>
      </div>
    </div>
  </div>;
}
