import {createContext,useContext,useEffect,useRef,useState,type FormEvent,type ReactNode} from 'react';
import {createClient,type SupabaseClient} from '@supabase/supabase-js';
import {useQueryClient} from '@tanstack/react-query';
import {api,post,setAccessTokenProvider} from './api';
import {MfaGate} from './MfaGate';
import './auth.css';
export type Role='viewer'|'planner'|'officer'|'admin';
export type ProfileDetails={designation:string;department:string;location:string};
export type Identity={id:string;email:string;name?:string;date_of_birth?:string;designation?:string;department?:string;location?:string;created_at?:string;last_sign_in_at?:string;email_confirmed?:boolean;role:Role;division:string;aal?:string;mfa_required?:boolean;mfa_policy_enabled?:boolean;mfa_enrolled?:boolean;access_pending?:boolean};
type Config={mode:'demo'|'supabase';supabase_url:string;publishable_key:string;division:string;public_signup_enabled?:boolean;collect_date_of_birth?:boolean};
const IdentityContext=createContext<Identity>({id:'',email:'',role:'viewer',division:''});
export const useIdentity=()=>useContext(IdentityContext);
type Actions={auth:SupabaseClient|null;refreshIdentity:()=>Promise<void>;changePassword:()=>void;signOut:()=>Promise<void>;updateProfile:(name:string,removeDob?:boolean,details?:ProfileDetails)=>Promise<void>;demo:boolean};
const ActionsContext=createContext<Actions>({auth:null,refreshIdentity:async()=>{},changePassword:()=>{},signOut:async()=>{},updateProfile:async()=>{},demo:true});
export const useAuthActions=()=>useContext(ActionsContext);
export function usePermission(role:Role){return ['viewer','planner','officer','admin'].indexOf(useIdentity().role)>=['viewer','planner','officer','admin'].indexOf(role)}
export function RoleNotice(){const {role}=useIdentity();return <p className="role-notice">{role==='viewer'?'Read-only access. Planner access is required to edit inputs or generate plans.':role==='planner'?'Planner access. Officer access is required to validate, benchmark, approve and finalize work.':role==='officer'?'Officer access. Administrator access is required to manage users and automation.':'Administrator access. Operational decisions require explicit review.'}</p>}
const logo=new URL('../assets0/logo.png',import.meta.url).href;

export function AuthBoundary({children}:{children:ReactNode}){
 const cache=useQueryClient(),epoch=useRef(0),identityRef=useRef<Identity|null>(null);
 const [config,setConfig]=useState<Config|null>(null),[auth,setAuth]=useState<SupabaseClient|null>(null),[identity,setIdentity]=useState<Identity|null>(null);
 const [loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const [email,setEmail]=useState(''),[name,setName]=useState(''),[dob,setDob]=useState(''),[role,setRole]=useState<Role>('viewer');
 const [password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[recovery,setRecovery]=useState(false),[register,setRegister]=useState(false);
 const applyIdentity=async(user:Identity|null)=>{const old=identityRef.current;if(old?.id!==user?.id||old?.role!==user?.role||old?.aal!==user?.aal){await cache.cancelQueries();cache.clear()}identityRef.current=user;setIdentity(user)};
 const refresh=async()=>{const current=++epoch.current;try{const user=await api<Identity>('/api/auth/me');if(current===epoch.current){await applyIdentity(user);setError('')}}catch(e){if(current===epoch.current){await applyIdentity(null);setError(e instanceof Error?e.message:String(e))}}};
 useEffect(()=>{
  let live=true,unsubscribe=()=>{};let client:SupabaseClient|null=null;
  api<Config>('/api/auth/config').then(c=>{
   if(!live)return;setConfig(c);
   if(c.mode==='demo'){void applyIdentity({id:'local-demo',email:'',role:'admin',division:c.division});setLoading(false);return}
   let invited=new URLSearchParams(window.location.hash.slice(1)).get('type')==='invite';
   client=createClient(c.supabase_url,c.publishable_key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});
   const active=client;setAuth(active);
   setAccessTokenProvider(async()=>{const {data,error}=await active.auth.getSession();if(error)throw error;return data.session?.access_token||null});
   const {data}=active.auth.onAuthStateChange((event,session)=>{
    const current=++epoch.current;
    window.setTimeout(async()=>{if(!live||current!==epoch.current)return;
     if(event==='SIGNED_OUT'||!session){await applyIdentity(null);setRecovery(false);setLoading(false);return}
     if(event==='PASSWORD_RECOVERY'||invited){setRecovery(true);invited=false}
     try{const user=await api<Identity>('/api/auth/me');if(live&&current===epoch.current){await applyIdentity(user);setError('')}}catch(e){if(live&&current===epoch.current){await applyIdentity(null);setError(e instanceof Error?e.message:String(e))}}finally{if(live&&current===epoch.current)setLoading(false)}
    },0);
   });unsubscribe=()=>data.subscription.unsubscribe();
  }).catch(e=>{if(live){setError(String(e));setLoading(false)}});
  return()=>{live=false;++epoch.current;unsubscribe();client?.auth.stopAutoRefresh();setAccessTokenProvider(async()=>null)};
 },[cache]);
 useEffect(()=>{if(!auth||!identity)return;const check=()=>{if(document.visibilityState==='visible')void refresh()};const timer=window.setInterval(check,30000);window.addEventListener('focus',check);return()=>{clearInterval(timer);window.removeEventListener('focus',check)}},[auth,identity?.id]);
 const clear=()=>{setError('');setNotice('');setPassword('');setConfirm('')};
 const signIn=async()=>{
  if(!auth)throw Error('Identity service unavailable.');
  const identifier=email.trim();
  if(identifier.includes('@'))return auth.auth.signInWithPassword({email:identifier,password});
  const session=await post<{access_token:string;refresh_token:string}>('/api/auth/username-login',{username:identifier,password});
  return auth.auth.setSession(session);
 };
 const submit=async(e:FormEvent)=>{e.preventDefault();if(!auth)return;setBusy(true);setError('');setNotice('');try{
  if((register||recovery)&&password!==confirm)throw Error('Passwords do not match');
  if(register&&(!name.trim()||(config?.collect_date_of_birth&&!dob)))throw Error('Complete the required profile fields');
  const result=recovery?await auth.auth.updateUser({password}):register?await auth.auth.signUp({email:email.trim(),password,options:{emailRedirectTo:window.location.origin+'/queue',data:{full_name:name.trim(),...(config?.collect_date_of_birth?{date_of_birth:dob}:{}),requested_role:role}}}):await signIn();
  if(result.error)throw result.error;setPassword('');setConfirm('');
  if(recovery){setRecovery(false);setNotice('Password updated.');await refresh()}else if(register){setRegister(false);setName('');setDob('');setRole('viewer');setNotice('Check your email to confirm your account. An administrator must approve your access.')}
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 const reset=async()=>{if(!auth||!email)return;setBusy(true);setError('');setNotice('');try{if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))throw Error('Enter your work email, not your username, to request a password reset.');const {error}=await auth.auth.resetPasswordForEmail(email.trim(),{redirectTo:window.location.origin+'/queue'});if(error)throw error;setNotice('If the account is eligible, a password reset email will arrive shortly.')}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 const changePassword=()=>{clear();setRecovery(true)};
 const signOut=async()=>{
  const result=await auth?.auth.signOut({scope:'local'});let warning='';
  if(result?.error){
   // The provider client can clear local storage even when remote revocation
   // fails. Distinguish that outcome from a session that is still present.
   const remaining=await auth?.auth.getSession();
   if(remaining?.error||remaining?.data.session)throw result.error;
   warning='Signed out on this device. Remote sign-out could not be confirmed by the identity service.';
  }
  ++epoch.current;await applyIdentity(null);clear();setNotice(warning);setEmail('');setRecovery(false);setRegister(false);setLoading(false);
 };
 const updateProfile=async(fullName:string,removeDob=false,details?:ProfileDetails)=>{if(!auth)throw Error('Profile editing is unavailable in demo mode.');const {error}=await auth.auth.updateUser({data:{full_name:fullName.trim(),...(details?{designation:details.designation.trim(),department:details.department.trim(),location:details.location.trim()}:{}),...(removeDob?{date_of_birth:null}:{})}});if(error)throw error;await refresh()};
 if(loading)return <div className="auth-loading" role="status">Connecting to your planning workspace…</div>;
 if(identity?.access_pending&&!recovery)return <main className="access-gate"><section className="access-card"><span className="section-overline">ACCOUNT REGISTERED</span><h1>Awaiting access approval</h1><p>{identity.email}</p><p>Your account is signed in. A division administrator must assign your RailBLOX access before you can open planning records.</p><button className="primary" onClick={refresh}>Check access again</button><button onClick={changePassword}>Set or change password</button>{error&&<p role="alert">{error}</p>}<button onClick={()=>void signOut().catch(e=>setError(e.message))}>Sign out</button></section></main>;
 if(identity?.mfa_required&&identity.aal!=='aal2'&&auth&&!recovery)return <MfaGate auth={auth} onVerified={refresh} onSignOut={signOut}/>;
 if(!identity||recovery||register)return <main className="auth-page"><div className="auth-intro"><div className="auth-logo"><img src={logo} alt="RailBLOX"/></div><p className="section-overline">Railway planning & coordination</p><h1>Every window.<br/>Every worksite.</h1><p>A shared workspace for maintenance priorities, evidence and officer-reviewed block planning.</p><div className="auth-division">Authorized personnel only</div></div>
  <div className="auth-signin"><form className="auth-card" onSubmit={submit}><p className="section-overline">DIVISION WORKSPACE</p><h2>{recovery?'Set your password':register?'Create an account':'Sign in'}</h2><p>{register?'An administrator must approve your requested role before you can access this division.':'Use the account provided by your division administrator.'}</p>
   {!recovery&&<label>{register?'Work email':'Username or work email'}<input type={register?'email':'text'} autoComplete={register?'email':'username'} autoCapitalize="none" spellCheck={false} required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/><small className="field-help">{register?'Registration requires an email address. Choose a unique username in your profile after access is approved.':'Use your work email, or the username saved in your profile.'}</small></label>}
   {register&&<><label>Full name<input autoComplete="name" required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label>{config?.collect_date_of_birth&&<label>Date of birth<input type="date" autoComplete="bday" required max={new Date().toISOString().slice(0,10)} value={dob} onChange={e=>setDob(e.target.value)}/></label>}<label>Requested role<select value={role} onChange={e=>setRole(e.target.value as Role)}>{['viewer','planner','officer','admin'].map(r=><option key={r} value={r}>{r[0].toUpperCase()+r.slice(1)}</option>)}</select><small>This request cannot grant permissions.</small></label></>}
   <label>{recovery||register?'New password':'Password'}<input type="password" autoComplete={recovery||register?'new-password':'current-password'} minLength={recovery||register?12:1} required value={password} onChange={e=>setPassword(e.target.value)}/></label>{(recovery||register)&&<label>Confirm password<input type="password" autoComplete="new-password" minLength={12} required value={confirm} onChange={e=>setConfirm(e.target.value)}/></label>}
   {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<button className="primary" disabled={busy||!auth}>{busy?'Please wait…':recovery?'Save password':register?'Create account':'Sign in to workspace'}</button>
   {!recovery&&!register&&<><button type="button" className="text-button" disabled={busy||!email||!auth} onClick={reset}>Forgot password?</button>{config?.public_signup_enabled&&<button type="button" className="text-button" disabled={busy||!auth} onClick={()=>{clear();setRegister(true)}}>New user? Create an account</button>}</>}
   {(register||recovery)&&<button type="button" className="text-button" disabled={busy} onClick={()=>{clear();setRegister(false);setRecovery(false)}}>Back to sign in</button>}{auth&&(identity||error||recovery)&&<button type="button" className="text-button" onClick={()=>void signOut().catch(e=>setError(e.message))}>Clear existing session</button>}
  </form></div></main>;
 return <IdentityContext.Provider value={identity}><ActionsContext.Provider value={{auth,refreshIdentity:refresh,changePassword,signOut,updateProfile,demo:config?.mode==='demo'}}>{children}</ActionsContext.Provider></IdentityContext.Provider>;
}
