import {useEffect,useRef} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from './api';
export type DeploymentStatus={revision:string;updates:string;realtime:string;source_connections:string;external_ai:string;user_administration:boolean;mfa_enforced:boolean;public_signup:boolean;database:string};
export function WorkspaceStatus(){
 const cache=useQueryClient(),previous=useRef('');
 const status=useQuery({queryKey:['workspace-status'],queryFn:()=>api<DeploymentStatus>('/api/status'),refetchInterval:30000,refetchOnWindowFocus:true});
 useEffect(()=>{const revision=status.data?.revision;if(!revision)return;if(previous.current&&previous.current!==revision)void cache.invalidateQueries({predicate:q=>!['workspace-status','admin-users','admin-audit'].includes(String(q.queryKey[0]))});previous.current=revision},[status.data?.revision,cache]);
 if(!status.error)return null;
 return <div className="workspace-sync" role="status"><span>Workspace updates unavailable.</span><button disabled={status.isFetching} onClick={()=>void status.refetch()}>{status.isFetching?'Retrying…':'Retry refresh'}</button></div>
}
