import {useState} from 'react';
import {LogOut} from 'lucide-react';
import {useAuthActions} from './Auth';

export function LogoutButton({label='Log out'}:{label?:string}){
  const {signOut,demo}=useAuthActions();const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const logout=async()=>{setBusy(true);setError('');try{await signOut()}catch(e){setError(e instanceof Error?e.message:'Unable to log out. Please retry.')}finally{setBusy(false)}};
  return <div className="logout-control"><button type="button" disabled={busy||demo} title={demo?'No authenticated session in local demo mode':undefined} onClick={()=>void logout()}><LogOut size={15} aria-hidden="true"/>{busy?'Logging out…':label}</button>{error&&<p role="alert">{error}</p>}</div>;
}
