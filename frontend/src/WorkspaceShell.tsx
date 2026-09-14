import {useState, type ReactNode} from 'react';
import {NavLink, useLocation, useSearchParams} from 'react-router-dom';
import {ArrowRight, ChevronRight, Menu, X} from 'lucide-react';
import type {Context, Snapshot} from './types';

const logo = new URL('../assets0/logo.png', import.meta.url).href;
const logoWithTagline = new URL('../assets0/Logowtag.png', import.meta.url).href;
const links = [
  {path: '/planner', label: 'Planner'},
  {path: '/tasks', label: 'Maintenance'},
  {path: '/availability', label: 'Availability'},
  {path: '/data', label: 'Data review'},
  {path: '/opportunities', label: 'Opportunities'},
  {path: '/disruptions', label: 'Disruption lab'},
  {path: '/benchmarks', label: 'Results'},
];

export function WorkspaceShell({children, context, corridorId, onCorridor, snapshot}: {
  children: ReactNode;
  context?: Context;
  corridorId: string;
  onCorridor: (id: string) => void;
  snapshot?: Snapshot;
}) {
  const location = useLocation();
  const [params] = useSearchParams();
  const [menuOpen, setMenuOpen] = useState(false);
  const supportLinks=[{path:'/queue',label:'Block queue'},{path:'/operations',label:'Operations'},{path:'/insights',label:'Insights'},{path:'/reports',label:'Reporting'}];
  const page = [...links,...supportLinks,{path:'/profile',label:'Your profile'},{path:'/admin/users',label:'User access'}].find(link => link.path === location.pathname);
  const stations = snapshot?.sections.filter(section => section.line === 'UP') || [];
  const plannerUrl = {pathname: '/queue', search: params.toString()};

  return (
    <div className="app railway-site">
      <a className="skip-link" href="#workspace-content">Skip to workspace</a>
      <header className="site-header">
        <div className="masthead">
          <NavLink className="masthead-brand" to={plannerUrl} aria-label="RaILBLOX home" onClick={() => setMenuOpen(false)}>
            <span className="masthead-logo"><img src={logo} alt="RaILBLOX" width="860" height="264"/></span>
            <span className="brand-purpose">Railway maintenance planning</span>
          </NavLink>
          <div className="masthead-title"><span>PLAN. COORDINATE. MAINTAIN.</span><strong>Every window. Every worksite.</strong></div>
          <label className="network-picker"><span>PLANNING NETWORK</span><select aria-label="Corridor" value={corridorId} onChange={event => onCorridor(event.target.value)}>
            {context?.corridors.map(corridor => <option key={corridor.id} value={corridor.id}>{corridor.name}</option>)}
          </select></label>
          <button className="mobile-menu-toggle" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={20}/> : <Menu size={20}/>}<span>{menuOpen ? 'Close' : 'Menu'}</span></button>
        </div>
        <div className="navigation-band">
          <div className="navigation-inner">
            <nav id="primary-navigation" className={menuOpen ? 'primary-navigation is-open' : 'primary-navigation'} aria-label="Main navigation">
              {links.map(({path, label}) => <NavLink key={path} to={{pathname: path, search: params.toString()}} onClick={() => setMenuOpen(false)}><span>{label}</span></NavLink>)}
            </nav>
            <span className="navigation-environment"><span/>Demonstration workspace</span>
          </div>
        </div>
        <nav className="decision-navigation" aria-label="Decision support"><span>DECISION SUPPORT</span>{supportLinks.map(link=><NavLink key={link.path} to={{pathname:link.path,search:params.toString()}}>{link.label}</NavLink>)}</nav>
        <div className="network-strip">
          <div className="breadcrumb"><span>RailBLOX</span><ChevronRight size={13}/><strong>{page?.label || 'Planner'}</strong></div>
          <div className="network-route"><strong>{stations[0]?.origin || '—'}</strong><span className="network-route-line"/><strong>{stations.at(-1)?.destination || '—'}</strong><span className="network-section-count">{snapshot?.sections.length || 0} directed sections</span></div>
          <span className="network-time">Asia/Kolkata · IST</span>
        </div>
      </header>
      <div className="main-column">{children}</div>
      <footer className="site-footer">
        <NavLink className="footer-brand" to={plannerUrl} aria-label="RaILBLOX planner"><img src={logoWithTagline} alt="RaILBLOX automated railway block management system" width="860" height="264"/></NavLink>
        <p>Connected planning for railway maintenance.<span>Synthetic data · Local planning prototype</span></p>
        <NavLink to={plannerUrl}>Planning workspace <ArrowRight size={16}/></NavLink>
      </footer>
    </div>
  );
}
