export async function onRequestGet({request,env}) {
 const date=new URL(request.url).searchParams.get('date');
 if(date&&(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+'T00:00:00Z'))||new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date))return Response.json({error:'invalid_date'},{status:400});
 const data=await env.TB.get('rooton:briefing:us:'+(date||'latest'),{type:'json',cacheTtl:60});
 if(!data)return Response.json({error:'briefing_not_found'},{status:404,headers:{'Cache-Control':'no-store'}});
 const listing=await env.TB.list({prefix:'rooton:briefing:us:',limit:1000});
 const dates=listing.keys.map(k=>k.name.split(':').at(-1)).filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)).sort().reverse().slice(0,90);
 return Response.json({...data,available_dates:dates},{headers:{'Cache-Control':'public, max-age=60','X-Content-Type-Options':'nosniff'}});
}
