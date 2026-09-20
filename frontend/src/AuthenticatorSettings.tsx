import {useState,type FormEvent} from 'react';
import {useAuthActions,useIdentity} from './Auth';
import {Panel} from './components';

export function AuthenticatorSettings(){
  const {auth,refreshIdentity,demo}=useAuthActions(),identity=useIdentity();
  const [setup,setSetup]=useState<{id:string;qr:string;secret:string}|null>(null);
  const [code,setCode]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const enable=async()=>{if(!auth)return;setBusy(true);setError('');try{
    const factors=await auth.auth.mfa.listFactors();if(factors.error)throw factors.error;
    if(factors.data.totp.some(f=>f.status==='verified')){await refreshIdentity();return}
    const {data,error}=await auth.auth.mfa.enroll({factorType:'totp',friendlyName:'RailBLOX '+new Date().toISOString()});
    if(error)throw error;setSetup({id:data.id,qr:data.totp.qr_code,secret:data.totp.secret});
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const verify=async(event:FormEvent)=>{event.preventDefault();if(!auth||!setup)return;setBusy(true);setError('');try{
    const {error}=await auth.auth.mfa.challengeAndVerify({factorId:setup.id,code});if(error)throw error;
    setSetup(null);setCode('');await refreshIdentity();
  }catch(e){setCode('');setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const cancel=async()=>{if(!auth||!setup)return;setBusy(true);setError('');try{
    // Only this component's unfinished enrollment is eligible for cancellation.
    const factors=await auth.auth.mfa.listFactors();if(factors.error)throw factors.error;
    if(factors.data.totp.some(f=>f.id===setup.id&&f.status==='verified')){setSetup(null);setCode('');await refreshIdentity();return}
    const {error}=await auth.auth.mfa.unenroll({factorId:setup.id});if(error)throw error;
    setSetup(null);setCode('');
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  return <Panel title="Authenticator (MFA)" className="authenticator-settings"><div className="profile-card">
    {identity.mfa_enrolled?<><p role="status"><strong>MFA is enabled for your account.</strong> New password sign-ins require a code from your authenticator, even when mandatory enrollment is off.</p><p className="profile-intro">Keep access to your authenticator. Contact your division administrator for recovery if your device is lost.</p></>:<><p className="profile-intro">Add a second sign-in step with Google Authenticator, Microsoft Authenticator or another TOTP app. Setup becomes active only after you verify a code. Other sessions may be signed out when enrollment is verified.</p>{setup?<form className="authenticator-form" onSubmit={verify}><p>Scan this QR code, then enter the six-digit code from your app.</p><img className="mfa-qr" src={setup.qr} alt="Authenticator enrollment QR code"/><details><summary>Enter setup key manually</summary><code>{setup.secret}</code><p>Keep this key private. Do not include it in screenshots or support messages.</p></details><label>Authentication code<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} required/></label><div className="toolbar"><button className="primary" disabled={busy||code.length!==6}>{busy?'Please wait…':'Verify and enable MFA'}</button><button type="button" disabled={busy} onClick={()=>void cancel()}>Cancel setup</button></div></form>:<button className="primary" disabled={demo||busy} onClick={()=>void enable()}>{busy?'Checking authenticator…':'Enable MFA'}</button>}</>}
    {error&&<p className="error" role="alert">{error}</p>}
  </div></Panel>;
}
