import {useState} from 'react';
import {NavLink} from 'react-router-dom';
import {Building2,KeyRound,ShieldCheck,UserRound} from 'lucide-react';
import {Panel} from './components';
import {useAuthActions,useIdentity} from './Auth';
import './profile.css';

const roleCopy={
  viewer:'Read schedules, evidence and reports, with export access.',
  planner:'Prepare work packages, review inputs, run planning and draft recommendations.',
  officer:'Review, approve or reject recommendations, finalize commitments and record outcomes.',
  admin:'Manage this deployment, configure automation and inspect the audit history.'
} as const;

export function ProfilePage(){
  const identity=useIdentity();
  const {changePassword,signOut,updateProfile,demo}=useAuthActions();
  const [name,setName]=useState(identity.name||''),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const save=async(removeDob=false)=>{setBusy(true);setError('');try{await updateProfile(name,removeDob);setMessage(removeDob?'Date of birth removed from your profile.':'Profile saved.')}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const initials=(identity.name||identity.email||identity.id).split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase();
  return <div className="profile-page">
    <div className="page-heading profile-heading"><div><div className="eyebrow"><span/>ACCOUNT & ACCESS</div><h1>Your profile</h1><p>Review the identity and permissions used to access this RailBLOX workspace.</p></div><div className="profile-avatar" aria-hidden="true">{initials}</div></div>
    {message&&<p role="status" className="validation-pass">{message}</p>}{error&&<p role="alert" className="error">{error}</p>}
    <div className="profile-grid">
      <Panel title="Account identity"><div className="profile-card">
        <div className="profile-row"><UserRound size={18}/><div><span className="profile-label">Name</span><strong>{identity.name||'Not provided'}</strong></div></div>
        <div className="profile-row"><UserRound size={18}/><div><span className="profile-label">Email</span><strong>{identity.email||'Local demonstration account'}</strong></div></div>
        {identity.date_of_birth&&<div className="profile-row"><div><span className="profile-label">Date of birth</span><strong>{identity.date_of_birth}</strong></div></div>}
        <div className="profile-row"><Building2 size={18}/><div><span className="profile-label">Authorized division</span><strong>{identity.division}</strong></div></div>
        <div className="profile-row"><ShieldCheck size={18}/><div><span className="profile-label">RailBLOX role</span><strong className="profile-role">{identity.role}</strong><p>{roleCopy[identity.role]}</p></div></div>
        <div className="profile-row profile-id"><div><span className="profile-label">Account ID</span><code>{identity.id}</code></div></div>
      </div></Panel>
      <Panel title="Profile & security"><div className="profile-actions"><form onSubmit={e=>{e.preventDefault();void save()}}><label>Full name<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label><button disabled={demo||busy||!name.trim()} className="primary">Save profile</button></form><p>Session verification: {identity.aal==='aal2'?'Authenticator verified':'Password session'}.</p><p>Your password is managed securely by Supabase Auth. Use a reset link or update it while signed in.</p><button disabled={demo} className="primary" onClick={changePassword}><KeyRound size={16}/>Change password</button><button disabled={demo} onClick={signOut}>Sign out</button>{!demo&&<details><summary>Profile privacy</summary><p>You can remove a previously supplied birth date. Account access and audit records are retained separately under the deployment retention policy.</p><button disabled={busy} onClick={()=>save(true)}>Remove stored date of birth</button></details>}</div></Panel>
    </div>
    <div className="profile-note"><strong>Need different access?</strong><span>Ask a RailBLOX administrator to update your role or division. Permissions refresh within 30 seconds or when you return to this tab.</span></div>
    <div className="profile-links"><NavLink className="text-button profile-back" to="/queue">← Back to block queue</NavLink>{identity.role==='admin'&&<NavLink className="text-button profile-back" to="/admin/users">Manage user access →</NavLink>}</div>
  </div>;
}
