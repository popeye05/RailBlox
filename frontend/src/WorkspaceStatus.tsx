import {useEffect,useRef} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from './api';
export type DeploymentStatus={revision:string;updates:string;realtime:string;source_connections:string;external_ai:string;user_administration:boolean;mfa_enforced:boolean;public_signup:boolean;database:string};
export function WorkspaceStatus(){
 const cache=useQueryClient(),previous=useRef('');
 const status=useQuery({queryKey:['workspace-status'],queryFn:()=>api<DeploymentStatus>('/api/status'),refetchInterval:30000,refetchOnWindowFocus:true});
 useEffect(()=>{const revision=status.data?.revision;if(!revision)return;if(previous.current&&previous.current!==revision)void cache.invalidateQueries({predicate:q=>!['workspace-status','admin-users','admin-audit'].includes(String(q.queryKey[0]))});previous.current=revision},[status.data?.revision,cache]);
 return <div className="workspace-sync" role="status"><span>{status.error?'Workspace refresh interrupted':status.isPending?'Checking workspace updates…':'Workspace checks every 30s'}</span><span>{status.dataUpdatedAt?`Last checked ${new Date(status.dataUpdatedAt).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'})}`:''}</span>{status.error&&<button onClick={()=>status.refetch()}>Retry refresh</button>}</div>
}
