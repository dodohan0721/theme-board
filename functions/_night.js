export async function nightResponse(env) {
 const d=await env.TB.get("rooton:night:state",{type:"json",cacheTtl:30});
 const now=Date.now(), utc=new Date(now), open=utc.getUTCDay()>=1&&utc.getUTCDay()<=5&&utc.getUTCHours()>=9&&utc.getUTCHours()<21;
 const data=d||{last:null,history:[],market:"KRX야간선물",timezone:"Asia/Seoul"};
 const age=data.observed_at?(now-Date.parse(data.observed_at))/1000:null;
 const status=!d?"not_connected":!open?"closed":age!==null&&age>=0&&age<180?"receiving":d.last_error?"error":d.last?"stale":"waiting";
 return Response.json({...data,status,configured:!!d,market_open:open,age_seconds:age===null?null:Math.max(0,Math.floor(age))},
 {headers:{"Cache-Control":"public, max-age=15","X-Content-Type-Options":"nosniff"}});
}
