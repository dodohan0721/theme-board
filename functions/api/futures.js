import { nightResponse } from '../_night.js';
export async function onRequestGet({request,env}) {
 const date=new URL(request.url).searchParams.get('date');
 if(!date)return nightResponse(env);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+'T00:00:00Z'))||new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date)return Response.json({error:'invalid_date'},{status:400});
 const current=await env.TB.get('rooton:night:state',{type:'json',cacheTtl:30});
 const data=current?.history_session===date?current:await env.TB.get('rooton:night:archive:'+date,{type:'json',cacheTtl:60});
 if(!data)return Response.json({history:[],last:null,status:'no_history',history_session:date,configured:!!current},{headers:{'Cache-Control':'public, max-age=30'}});
 return Response.json({...data,status:'archived',configured:true},{headers:{'Cache-Control':'public, max-age=30','X-Content-Type-Options':'nosniff'}});
}
