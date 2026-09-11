import {createContext,useContext,useEffect,useState,useRef,type ReactNode,type FormEvent} from 'react';
import {createClient,type SupabaseClient} from '@supabase/supabase-js';
import {useQueryClient} from '@tanstack/react-query';
import {api,setAccessTokenProvider,authenticatedFetch,API} from './api';
import './auth.css';

type Identity={id:string;role:'viewer'|'planner'|'officer'|'admin';division:string};
type Config={mode:'demo'|'supabase';supabase_url:string;publishable_key:string;division:string};
const IdentityContext=createContext<Identity>({id:'local-demo',role:'admin',division:'demo'});
export const useIdentity=()=>useContext(IdentityContext);
export function usePermission(role:Identity['role']){return ['viewer','planner','officer','admin'].indexOf(useIdentity().role)>=['viewer','planner','officer','admin'].indexOf(role)}
const logo=new URL('../assets0/logo.png',import.meta.url).href;

export function AuthBoundary({children}:{children:ReactNode}){
 const cache=useQueryClient();
 const authEpoch=useRef(0);
 const [config,setConfig]=useState<Config|null>(null),[auth,setAuth]=useState<SupabaseClient|null>(null);
 const [identity,setIdentity]=useState<Identity|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[recovery,setRecovery]=useState(false);
 useEffect(()=>{
  let live=true;let unsubscribe=()=>{};
  api<Config>('/api/auth/config').then(c=>{
   if(!live)return;setConfig(c);
   if(c.mode==='demo'){setIdentity({id:'local-demo',role:'admin',division:c.division});setLoading(false);return}
   const client=createClient(c.supabase_url,c.publishable_key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});
   setAuth(client);setAccessTokenProvider(async()=>{const {data,error}=await client.auth.getSession();if(error)throw error;return data.session?.access_token||null});
   const {data}=client.auth.onAuthStateChange((event,session)=>{
    const epoch=++authEpoch.current;
    // Defer work outside the auth callback to avoid acquiring the client's auth lock recursively.
    window.setTimeout(async()=>{
     if(!live||epoch!==authEpoch.current)return;
     if(event==='SIGNED_OUT'||!session){cache.clear();setIdentity(null);setRecovery(false);setLoading(false);return}
     if(event==='PASSWORD_RECOVERY')setRecovery(true);
     try{const user=await api<Identity>('/api/auth/me');if(live&&epoch===authEpoch.current){setIdentity(user);setError('')}}catch(e){if(live&&epoch===authEpoch.current){cache.clear();setIdentity(null);setError(String(e))}}finally{if(live&&epoch===authEpoch.current)setLoading(false)}
    },0);
   });unsubscribe=()=>data.subscription.unsubscribe();
  }).catch(e=>{if(live){setError(String(e));setLoading(false)}});
  return()=>{live=false;unsubscribe()};
 },[cache]);
 const submit=async(e:FormEvent)=>{e.preventDefault();if(!auth)return;setBusy(true);setError('');setNotice('');try{
  const result=recovery?await auth.auth.updateUser({password}):await auth.auth.signInWithPassword({email,password});
  if(result.error)throw result.error;setPassword('');if(recovery){setRecovery(false);setNotice('Password updated.')}
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 const reset=async()=>{if(!auth||!email)return;setBusy(true);setError('');try{const {error}=await auth.auth.resetPasswordForEmail(email,{redirectTo:window.location.origin+'/queue'});if(error)throw error;setNotice('If the account is eligible, a password reset email will arrive shortly.')}catch(e){setError(String(e))}finally{setBusy(false)}};
 const signOut=async()=>{authEpoch.current++;await cache.cancelQueries();cache.clear();setIdentity(null);setRecovery(false);setLoading(true);try{const result=await auth?.auth.signOut({scope:'local'});if(result?.error)setError(result.error.message)}finally{setLoading(false)}};
 if(loading)return <div className="auth-loading" role="status">Connecting to your planning workspace…</div>;
 if(!identity||recovery)return <main className="auth-page"><div className="auth-intro"><div className="auth-logo"><img src={logo} alt="RailBLOX"/></div><p className="section-overline">Railway planning & coordination</p><h1>Every window.<br/>Every worksite.</h1><p>A shared workspace for maintenance priorities, evidence and officer-reviewed block planning.</p><div className="auth-division">Authorized access · {config?.division||'Connecting'}</div></div><form className="auth-card" onSubmit={submit}><p className="section-overline">Officer workspace</p><h2>{recovery?'Set your password':'Sign in'}</h2><p>Use the account provided by your division administrator.</p>{!recovery&&<label>Work email<input type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label>}<label>{recovery?'New password':'Password'}<input type="password" autoComplete={recovery?'new-password':'current-password'} minLength={recovery?12:1} required value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<button className="primary" disabled={busy||!auth}>{busy?'Please wait…':recovery?'Save password':'Sign in to workspace'}</button>{!recovery&&<button type="button" className="text-button" disabled={busy||!email||!auth} onClick={reset}>Forgot password?</button>}{auth&&<button type="button" className="text-button" onClick={signOut}>Clear existing session</button>}{!config&&<button type="button" onClick={()=>window.location.reload()}>Retry connection</button>}</form></main>;
 return <IdentityContext.Provider value={identity}>{config?.mode==='supabase'&&<div className="account-strip"><span>{identity.division} · {identity.role}</span><div><button onClick={()=>{setPassword('');setRecovery(true)}}>Change password</button><button onClick={signOut}>Sign out</button></div></div>}{children}</IdentityContext.Provider>;
}

export function DownloadLink({href,children,className,download:_download}:{href:string;children:ReactNode;className?:string;download?:boolean}){
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 return <><a className={className} href={href} aria-disabled={busy} onClick={async e=>{e.preventDefault();if(busy)return;setBusy(true);setError('');try{
  if(!href.startsWith(API+'/'))throw Error('Invalid export target');
  const response=await authenticatedFetch(href.slice(API.length));
  if(!response.ok){const data=await response.json();throw Error(data.message||'Export failed')}
  const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||'railblox-export.json';link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){setError(String(e))}finally{setBusy(false)}}}>{busy?'Preparing download…':children}</a>{error&&<span role="alert" className="error">{error}</span>}</>;
}
