import type{ApiSession,JobEvent,Result,Chat}from './types';
const base=process.env.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8001';
export class ApiError extends Error{constructor(public status:number,public code:string){super(code)}}
export async function call<T>(path:string,session?:ApiSession,init:RequestInit={}):Promise<T>{
 const headers=new Headers(init.headers);if(session)headers.set('Authorization',`Bearer ${session.token}`);if(init.body)headers.set('Content-Type','application/json');
 const response=await fetch(base+path,{...init,headers});if(!response.ok){let code='request_failed';try{code=(await response.json()).detail||code}catch{}throw new ApiError(response.status,code)}return response.json();
}
export function health(){return call<{ready:boolean;mode:'demo'|'live';error?:string}>('/health')}
export function createSession(){return call<ApiSession>('/sessions',undefined,{method:'POST'})}
export function getSession(s:ApiSession){return call<{result:Result|null;messages:Chat[];active_job:string|null}>(`/sessions/${s.id}`,s)}
export function send(s:ApiSession,message:string,id:string){return call<{job_id:string}>(`/sessions/${s.id}/messages`,s,{method:'POST',body:JSON.stringify({message,request_id:id})})}
export async function watch(s:ApiSession,job:string,onEvent:(e:JobEvent)=>void,signal:AbortSignal){
 let cursor=0;for(let attempt=0;attempt<4;attempt++){
  try{
   const response=await fetch(`${base}/jobs/${job}/events?after=${cursor}`,{headers:{Authorization:`Bearer ${s.token}`},signal});
   if(!response.ok)throw new ApiError(response.status,'events_unavailable');
   const reader=response.body!.getReader();let buffer='';const decoder=new TextDecoder();
   while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let at:number;
    while((at=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,at);buffer=buffer.slice(at+2);const data=block.split('\n').find(l=>l.startsWith('data: '));if(!data)continue;const e=JSON.parse(data.slice(6))as JobEvent;if(e.id<=cursor)continue;cursor=e.id;onEvent(e);if(e.type==='completed'||e.type==='failed'){await reader.cancel();return}}
   }
  }catch(error){if(signal.aborted)throw error}
  const state=await call<{status:string;events:JobEvent[]}>(`/jobs/${job}`,s,{signal});
  for(const e of state.events){if(e.id>cursor){cursor=e.id;onEvent(e)}}
  if(state.status==='completed'||state.status==='failed')return;
  await new Promise(r=>setTimeout(r,500));
 }throw new ApiError(503,'events_disconnected');
}
export async function download(s:ApiSession){const response=await fetch(base+`/sessions/${s.id}/export`,{headers:{Authorization:`Bearer ${s.token}`}});if(!response.ok)throw new ApiError(response.status,'export_failed');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='tripbuddy-course.md';a.click();URL.revokeObjectURL(url)}
