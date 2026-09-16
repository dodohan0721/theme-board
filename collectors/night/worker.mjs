const KEY = "rooton:night:state";
const AUTH = "rooton:night:auth";
const KIS = "https://openapi.koreainvestment.com:9443";
const WS = "http://ops.koreainvestment.com:21000";
const TR = "H0MFCNT0";
export function kst(ms = Date.now()) { return new Date(ms + 32400000).toISOString().slice(0,19).replace("T"," "); }
export function session(ms) { return new Date(ms + 32400000 - 21600000).toISOString().slice(0,10); }
export function isOpen(ms = Date.now()) {
 const d = new Date(ms), day = d.getUTCDay(), hour = d.getUTCHours();
 return day >= 1 && day <= 5 && hour >= 9 && hour < 21;
}
export function chooseCode(rows) {
 const valid = rows.filter(r => /^A01\d{3}$|^101[A-Z0-9]{3,5}$/.test(r.futs_shrn_iscd || "") && !/미니|스프레드|코스닥|변동성/.test(r.hts_kor_isnm || ""));
 valid.sort((a,b) => Number(b.acml_vol || 0) - Number(a.acml_vol || 0));
 if (!valid.length) throw new Error("standard_kospi200_contract_missing");
 return { code: valid[0].futs_shrn_iscd, name: valid[0].hts_kor_isnm, day_close: Number(valid[0].futs_prpr) };
}
export function parseTick(raw, code, now = Date.now()) {
 const p = String(raw).split("|");
 if (p[0] !== "0" || p[1] !== TR || p.length < 4) return null;
 const v = p[3].split("^"), hh = v[1];
 if (v[0] !== code || !/^\d{6}$/.test(hh || "")) return null;
 const hour = Number(hh.slice(0,2));
 if (hour >= 6 && hour < 18) return null;
 const last = Number(v[5]);
 if (!Number.isFinite(last) || last <= 0) return null;
 const date = kst(now).slice(0,10), clock = hh.slice(0,2)+":"+hh.slice(2,4)+":"+hh.slice(4,6);
 let at = Date.parse(date+"T"+clock+"+09:00");
 if (at-now > 43200000) at -= 86400000;
 if (now-at > 43200000) at += 86400000;
 if (Math.abs(now-at) > 120000) return null;
 const signed = n => Math.abs(Number(n) || 0) * (["4","5"].includes(v[3]) ? -1 : 1);
 return {code,ts:kst(at),observed_at:new Date(at).toISOString(),time:clock,last,
  diff:signed(v[2]),rate:signed(v[4]),open:Number(v[6])||null,high:Number(v[7])||null,low:Number(v[8])||null,
  volume:Number(v[10])||0,market:"KRX야간선물",source:"KIS H0MFCNT0",timezone:"Asia/Seoul"};
}
export function mergeTick(previous, tick) {
 const sess = session(Date.parse(tick.observed_at)), minute = tick.ts.slice(0,16), points = new Map();
 const rows = previous && previous.code===tick.code && previous.history_session===sess ? previous.history || [] : [];
 for (const p of rows.concat([tick])) {
  const at = Date.parse(p.ts.replace(" ","T")+"+09:00");
  if (!Number.isFinite(at) || at>Date.parse(tick.observed_at) || session(at)!==sess || !Number.isFinite(p.last) || p.last<=0) continue;
  const key = p.ts.slice(0,16), old=points.get(key);
  if (!old || p.ts>=old.ts) points.set(key,{ts:p.ts,time:p.ts.slice(11,16),last:p.last});
 }
 return {...tick,history_session:sess,history:[...points.values()].sort((a,b)=>a.ts.localeCompare(b.ts)).slice(-720),
  sampling:"one_observed_trade_per_minute",interval_seconds:60};
}
export function publicState(state, now=Date.now()) {
 const d=state || {}, at=Date.parse(d.observed_at || ""), open=isOpen(now), has=Number.isFinite(d.last)&&d.last>0;
 const fresh=has && now-at>=0 && now-at<180000;
 return {...d,history:d.history||[],configured:true,market_open:open,
  status:!open?"closed":fresh?"receiving":d.last_error?"error":has?"stale":"waiting",
  age_seconds:has&&Number.isFinite(at)?Math.max(0,Math.floor((now-at)/1000)):null};
}
async function read(env,key) { try { return await env.TB.get(key,{type:"json",cacheTtl:30}); } catch { return null; } }
async function request(url, options) {
 const res=await fetch(url,{...options,signal:AbortSignal.timeout(15000)});
 if(!res.ok) throw new Error("kis_http_"+res.status);
 const d=await res.json();
 if(d.rt_cd && d.rt_cd!=="0") throw new Error("kis_"+String(d.msg_cd||"rejected").replace(/[^A-Z0-9_]/gi,""));
 return d;
}
async function auth(env) {
 let a=await read(env,AUTH) || {}, changed=false;
 if(!a.token || a.token_expire<Date.now()+600000) {
  const d=await request(KIS+"/oauth2/tokenP",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({grant_type:"client_credentials",appkey:env.KIS_APP_KEY,appsecret:env.KIS_APP_SECRET})});
  if(!d.access_token) throw new Error("rest_auth_failed");
  a.token=d.access_token; a.token_expire=Date.now()+Number(d.expires_in||86400)*1000-600000;changed=true;
 }
 if(!a.approval || a.approval_expire<Date.now()+600000) {
  const d=await request(KIS+"/oauth2/Approval",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({grant_type:"client_credentials",appkey:env.KIS_APP_KEY,secretkey:env.KIS_APP_SECRET})});
  if(!d.approval_key) throw new Error("websocket_auth_failed");
  a.approval=d.approval_key;a.approval_expire=Date.now()+82800000;changed=true;
 }
 if(!a.contract || a.contract_at<Date.now()-43200000) {
  const q=new URLSearchParams({FID_COND_MRKT_DIV_CODE:"F",FID_COND_SCR_DIV_CODE:"20503",FID_COND_MRKT_CLS_CODE:""});
  const d=await request(KIS+"/uapi/domestic-futureoption/v1/quotations/display-board-futures?"+q,{
   headers:{authorization:"Bearer "+a.token,appkey:env.KIS_APP_KEY,appsecret:env.KIS_APP_SECRET,tr_id:"FHPIF05030200",custtype:"P"}});
  a.contract=chooseCode(d.output||[]);a.contract_at=Date.now();changed=true;
 }
 if(changed) await env.TB.put(AUTH,JSON.stringify(a));
 return a;
}
async function observe(a, seconds) {
 const res=await fetch(WS,{headers:{Upgrade:"websocket"}});
 const ws=res.webSocket;
 if(!ws) throw new Error("websocket_upgrade_"+res.status);
 ws.accept();
 return await new Promise((resolve,reject)=>{
  let done=false, subscribed=false;
  const finish=(err,tick=null)=>{
   if(done)return;done=true;clearTimeout(timer);try{ws.close(1000,"sample complete");}catch{}
   if(err)reject(err);else resolve({subscribed,tick});
  };
  const timer=setTimeout(()=>finish(subscribed?null:new Error("subscription_timeout")),seconds*1000);
  ws.addEventListener("message",event=>{
   const raw=String(event.data);
   if(raw.startsWith("{")){
    let j;try{j=JSON.parse(raw);}catch{return;}
    if(j.header?.tr_id==="PINGPONG") { try{ws.send(raw);}catch{} return; }
    if(j.body?.rt_cd==="0") subscribed=true;
    else if(j.body?.rt_cd)finish(new Error("subscription_"+String(j.body.msg_cd||"rejected").replace(/[^A-Z0-9_]/gi,"")));
    return;
   }
   const tick=parseTick(raw,a.contract.code);
   if(tick) finish(null,tick);
  });
  ws.addEventListener("error",()=>finish(new Error("websocket_error")));
  ws.addEventListener("close",()=>{if(!done)finish(subscribed?null:new Error("websocket_closed"));});
  ws.send(JSON.stringify({header:{approval_key:a.approval,custtype:"P",tr_type:"1","content-type":"utf-8"},body:{input:{tr_id:TR,tr_key:a.contract.code}}}));
 });
}
export async function collect(env,{probe=false}={}) {
 if(!env.KIS_APP_KEY || !env.KIS_APP_SECRET) throw new Error("collector_secrets_missing");
 let state=await read(env,KEY) || {history:[],last:null,source:"KIS H0MFCNT0",market:"KRX야간선물",timezone:"Asia/Seoul"};
 if(!isOpen()&&!probe) {
  if(state.history?.length && state.archived_session!==state.history_session){
   await env.TB.put("rooton:night:archive:"+state.history_session,JSON.stringify(state),{expirationTtl:90*86400});
   state.archived_session=state.history_session;await env.TB.put(KEY,JSON.stringify(state));
  }
  return publicState(state);
 }
 try{
  const a=await auth(env), result=await observe(a,probe&&!isOpen()?5:35);
  const now=new Date().toISOString();
  if(result.tick){
   if(state.history?.length && state.history_session!==session(Date.parse(result.tick.observed_at)))
    await env.TB.put("rooton:night:archive:"+state.history_session,JSON.stringify(state),{expirationTtl:90*86400});
   state=mergeTick(state,result.tick);
  }
  state={...state,code:a.contract.code,name:"KOSPI200 "+a.contract.name,checked_at:now,
   subscription_verified_at:result.subscribed?now:state.subscription_verified_at,last_error:null,interval_seconds:60};
  await env.TB.put(KEY,JSON.stringify(state));
  return publicState(state);
 }catch(e){
  const safe=/^[a-z0-9_]+$/i.test(e.message)?e.message:"collector_connection_failed";
  state={...state,checked_at:new Date().toISOString(),last_error:safe};
  await env.TB.put(KEY,JSON.stringify(state));
  throw new Error(safe);
 }
}
export default {
 async scheduled(controller,env,ctx){
  ctx.waitUntil(collect(env).then(d=>console.log(JSON.stringify({status:d.status,points:d.history.length,last_ts:d.ts||null}))));
 },
 async fetch(request,env){
  const u=new URL(request.url);
  if(u.pathname==="/health"&&request.method==="GET") return Response.json(publicState(await read(env,KEY)),{headers:{"Cache-Control":"no-store"}});
  if(u.pathname==="/probe"&&request.method==="POST"&&env.PROBE_TOKEN&&request.headers.get("Authorization")==="Bearer "+env.PROBE_TOKEN){
   try { return Response.json(await collect(env,{probe:true})); }
   catch(e){ return Response.json({error:e.message},{status:502}); }
  }
  return new Response("Not found",{status:404});
 }
};
