import {useEffect,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,patch} from './api';
import {Panel} from './components';
import {useAuthActions} from './Auth';

type LoginName={username:string|null;enabled:boolean};
export function UsernameSettings(){
  const {demo}=useAuthActions();
  const query=useQuery({queryKey:['login-name'],queryFn:()=>api<LoginName>('/api/auth/username'),enabled:!demo});
  const [username,setUsername]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  useEffect(()=>{if(query.data)setUsername(query.data.username||'')},[query.data]);
  const dirty=username.trim().toLowerCase()!==(query.data?.username||'');
  return <Panel title="Sign-in username"><form className="profile-form" onSubmit={async e=>{
    e.preventDefault();setBusy(true);setError('');setMessage('');
    try{const saved=await patch<LoginName>('/api/auth/username',{username,expected_username:query.data?.username||null});setUsername(saved.username||'');await query.refetch();setMessage('Username saved. You can now sign in with it or your work email.')}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}
  }}>
    <p className="profile-intro">An optional, unique sign-in name for this workspace. Email remains required for registration and account recovery.</p>
    {query.isFetching&&!demo&&<p role="status">Loading username…</p>}
    {query.error&&<p className="error" role="alert">{query.error.message}<button type="button" onClick={()=>void query.refetch()}>Retry username</button></p>}
    <label>Username<input autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={32} pattern="[a-zA-Z][a-zA-Z0-9._\-]{2,31}" value={username} disabled={demo||!query.data?.enabled||busy} onChange={e=>{setUsername(e.target.value);setMessage('')}} aria-describedby="username-rules"/></label>
    <p className="profile-hint" id="username-rules">3–32 characters; start with a letter. Letters, numbers, dots, underscores and hyphens only. Names are case-insensitive. Changing your name frees the old one for another account.</p>
    {!demo&&query.data&&!query.data.enabled&&<p className="profile-hint">Your administrator must configure username sign-in on the backend. Email sign-in remains available.</p>}
    {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
    <button className="primary" disabled={demo||busy||!query.data?.enabled||!dirty||!username.trim()}>{busy?'Saving username…':'Save username'}</button>
  </form></Panel>;
}
