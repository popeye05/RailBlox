export const API=(import.meta as unknown as {env:{VITE_API_URL?:string}}).env.VITE_API_URL || 'http://127.0.0.1:8000';
let accessToken:()=>Promise<string|null>=async()=>null;
export function setAccessTokenProvider(provider:()=>Promise<string|null>){accessToken=provider}
export async function authenticatedFetch(path:string,options?:RequestInit){
  const token=await accessToken();const headers=new Headers(options?.headers);
  if(!(options?.body instanceof FormData))headers.set('Content-Type','application/json');
  if(token)headers.set('Authorization','Bearer '+token);
  return fetch(API+path,{...options,headers});
}
export async function api<T>(path:string,options?:RequestInit):Promise<T>{
  let response:Response;
  try{response=await authenticatedFetch(path,options)}catch{throw new Error('Planning service unavailable. Check your connection and backend configuration, then retry.');}
  const data=await response.json().catch(()=>{throw new Error(`Planning service returned an unreadable response (${response.status}). Retry or ask the administrator to check the server.`)});
  if(!response.ok)throw new Error(`${data.message||'Request failed'}${data.details?' · '+JSON.stringify(data.details):''} [${data.request_id||response.status}]`);
  return data as T;
}
export function post<T>(path:string,body:unknown={}){return api<T>(path,{method:'POST',body:JSON.stringify(body)})}
export function patch<T>(path:string,body:unknown={}){return api<T>(path,{method:'PATCH',body:JSON.stringify(body)})}
export async function job(path:string,body:unknown={}){
  const run=await post<{id:string}>(path,body);
  for(let attempt=0;attempt<240;attempt++){
    await new Promise(resolve=>setTimeout(resolve,Math.min(500+attempt*100,2000)));
    const state=await api<{status:string;result_id:string;error?:string}>(`/api/runs/${run.id}`);
    if(state.status==='succeeded')return state.result_id;
    if(state.status==='failed')throw new Error(state.error||'Operation failed. Retry after reviewing inputs.');
  }
  throw new Error(`Operation is still running. Run ${run.id}; refresh to check completed plans.`);
}
export function time(minute:number,anchor:string,withDate=false){return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false,...(withDate?{day:'2-digit',month:'short'}:{})}).format(new Date(new Date(anchor).getTime()+minute*60000))}
export function date(minute:number,anchor:string){return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',weekday:'short'}).format(new Date(new Date(anchor).getTime()+minute*60000))}
