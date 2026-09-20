import {useState,type FormEvent} from 'react';
import {useAuthActions,useIdentity} from './Auth';
import {Panel} from './components';

export function AuthenticatorSettings(){
  const {auth,refreshIdentity,demo}=useAuthActions(),identity=useIdentity();
  const [setup,setSetup]=useState<{id:string;qr:string;secret:string}|null>(null);
  const [code,setCode]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [removal,setRemoval]=useState<{id:string;name:string}[]|null>(null),[factorId,setFactorId]=useState('');
  const mandatory=identity.mfa_policy_enabled&&identity.role!=='viewer';
  const beginDisable=async()=>{if(!auth||mandatory)return;setBusy(true);setError('');setCode('');try{
    const {data,error}=await auth.auth.mfa.listFactors();if(error)throw error;
    const verified=data.totp.filter(f=>f.status==='verified').map((f,i)=>({id:f.id,name:f.friendly_name||`Authenticator ${i+1}`}));
    if(!verified.length){await refreshIdentity();return}
    setRemoval(verified);setFactorId(verified[0].id);
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const disable=async(event:FormEvent)=>{event.preventDefault();if(!auth||!removal||mandatory)return;setBusy(true);setError('');let removed=0;
    try{
      const verification=await auth.auth.mfa.challengeAndVerify({factorId,code});if(verification.error)throw verification.error;
      const factors=await auth.auth.mfa.listFactors();if(factors.error)throw factors.error;
      const verified=factors.data.totp.filter(f=>f.status==='verified');
      if(verified.length!==removal.length||verified.some(f=>!removal.some(r=>r.id===f.id))){setRemoval(null);throw new Error('Your authenticators changed. Select Disable MFA again to review them.')}
      // Remove only the confirmed factors, keeping the just-verified one until last.
      for(const factor of [...removal.filter(f=>f.id!==factorId),...removal.filter(f=>f.id===factorId)]){
        const {error}=await auth.auth.mfa.unenroll({factorId:factor.id});if(error)throw error;removed++;
      }
      setRemoval(null);
      const remaining=await auth.auth.mfa.listFactors();if(remaining.error)throw remaining.error;
      if(remaining.data.totp.some(f=>f.status==='verified'))throw new Error('An authenticator is still enabled. Review your security settings again.');
    }catch(e){setError(`${removed?'Some authenticators were removed. Check the current MFA status before trying again. ':''}${e instanceof Error?e.message:String(e)}`);if(removed)setRemoval(null)}
    finally{setCode('');try{await refreshIdentity()}catch{setError('Could not refresh MFA status. Reload your profile to check your account.')}setBusy(false)}
  };
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
    {identity.mfa_enrolled?<><p role="status"><strong>MFA is enabled for your account.</strong> Sign-in requires an authenticator code.</p>
      {removal?<form className="authenticator-form" onSubmit={disable} aria-label="Disable MFA confirmation">
        <p>This removes {removal.length===1?'your authenticator':`all ${removal.length} authenticators`} and allows password-only sign-in. Enter a fresh code to confirm.</p>
        {removal.length>1&&<label>Authenticator to verify<select value={factorId} onChange={e=>{setFactorId(e.target.value);setCode('')}} disabled={busy}>{removal.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>}
        <label>Authentication code<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} disabled={busy} required autoFocus/></label>
        <div className="toolbar"><button className="primary" disabled={busy||code.length!==6}>{busy?'Please wait…':'Confirm disable MFA'}</button><button type="button" disabled={busy} onClick={()=>{setRemoval(null);setCode('');setError('')}}>Cancel</button></div>
      </form>:<><button disabled={demo||busy||mandatory} onClick={()=>void beginDisable()}>Disable MFA</button>{mandatory&&<p className="profile-intro">MFA is required by your division policy.</p>}<p className="profile-intro">Lost your authenticator? Contact your division administrator.</p></>}
    </>:<><p className="profile-intro">Protect sign-in with an authenticator app. Verify a code to enable MFA; other sessions may be signed out.</p>{setup?<form className="authenticator-form" onSubmit={verify}><p>Scan this QR code, then enter the six-digit code from your app.</p><img className="mfa-qr" src={setup.qr} alt="Authenticator enrollment QR code"/><details><summary>Enter setup key manually</summary><code>{setup.secret}</code><p>Keep this key private. Do not include it in screenshots or support messages.</p></details><label>Authentication code<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} required/></label><div className="toolbar"><button className="primary" disabled={busy||code.length!==6}>{busy?'Please wait…':'Verify and enable MFA'}</button><button type="button" disabled={busy} onClick={()=>void cancel()}>Cancel setup</button></div></form>:<button className="primary" disabled={demo||busy} onClick={()=>void enable()}>{busy?'Checking authenticator…':'Enable MFA'}</button>}</>}
    {error&&<p className="error" role="alert">{error}</p>}
  </div></Panel>;
}
