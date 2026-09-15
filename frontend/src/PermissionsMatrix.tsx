import {useQuery} from '@tanstack/react-query';
import {Check, Minus} from 'lucide-react';
import {api} from './api';
import {useIdentity, type Role} from './Auth';

export const roleNames:Record<Role,string>={viewer:'Viewer',planner:'Planner',officer:'Officer',admin:'Administrator'};
export const roleDescriptions:Record<Role,string>={viewer:'Inspect schedules, source evidence and reports.',planner:'Prepare maintenance inputs and generate proposals.',officer:'Review decisions, approve commitments and record outcomes.',admin:'Manage access, review audit records and configure the division.'};
type Permissions={roles:Role[];capabilities:{id:string;label:string;role:Role}[]};

export function PermissionsMatrix(){
  const identity=useIdentity();
  const query=useQuery({queryKey:['permissions'],queryFn:()=>api<Permissions>('/api/auth/permissions'),staleTime:300000});
  if(query.isPending)return <p className="padded" role="status">Loading access permissions…</p>;
  if(query.error)return <div className="padded" role="alert"><p>{query.error.message}</p><button onClick={()=>query.refetch()}>Retry permissions</button></div>;
  return <div className="table-scroll"><table className="permissions-table"><caption>Division access by role. Your current role is {roleNames[identity.role]}.</caption><thead><tr><th scope="col">Capability</th>{query.data.roles.map(role=><th scope="col" key={role} className={role===identity.role?'your-role':''}>{roleNames[role]}{role===identity.role&&<small>Your role</small>}</th>)}</tr></thead><tbody>{query.data.capabilities.map(item=><tr key={item.id}><th scope="row">{item.label}</th>{query.data.roles.map(role=><td key={role} className={role===identity.role?'your-role':''}>{query.data.roles.indexOf(role)>=query.data.roles.indexOf(item.role)?<><Check size={16} aria-hidden="true"/><span className="sr-only">Allowed</span></>:<><Minus size={16} aria-hidden="true"/><span className="sr-only">Not allowed</span></>}</td>)}</tr>)}</tbody></table></div>;
}
