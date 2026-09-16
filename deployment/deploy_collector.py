"""Deploy with existing GitHub Secrets; never print credentials."""
import json, os, re, secrets, subprocess, sys, time, urllib.request, urllib.error
CONFIG = "collectors/night/wrangler.toml"
def run(args, **kwargs):
    subprocess.run(["npx","--yes","wrangler@4.131.2",*args],check=True,**kwargs)
def main():
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        print("Missing GitHub Secret: CLOUDFLARE_WORKERS_API_TOKEN",flush=True)
        raise RuntimeError("Workers deployment credential is missing")
    run(["deploy","--config",CONFIG])
    probe = secrets.token_urlsafe(32)
    body = json.dumps({"KIS_APP_KEY":os.environ["KIS_APP_KEY"],"KIS_APP_SECRET":os.environ["KIS_APP_SECRET"],"PROBE_TOKEN":probe})
    run(["secret","bulk","--config",CONFIG],input=body,text=True)
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/accounts/"+os.environ["CLOUDFLARE_ACCOUNT_ID"]+"/workers/subdomain",
        headers={"Authorization":"Bearer "+os.environ["CLOUDFLARE_API_TOKEN"],"User-Agent":"ROOTON-deployment-verifier/1.0"})
    with urllib.request.urlopen(req,timeout=30) as response:domain=json.load(response)["result"]["subdomain"]
    if not re.fullmatch(r"[a-zA-Z0-9-]+",domain):raise RuntimeError("Unexpected worker subdomain")
    url="https://rooton-night-collector."+domain+".workers.dev"
    req=urllib.request.Request(url+"/probe",data=b"{}",method="POST",
        headers={"Authorization":"Bearer "+probe,"Content-Type":"application/json","User-Agent":"ROOTON-deployment-verifier/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=55) as response:state=json.load(response)
            break
        except urllib.error.HTTPError as exc:
            try:code=json.loads(exc.read()).get("error","http_"+str(exc.code))
            except Exception:code="http_"+str(exc.code)
            safe=code if re.fullmatch(r"[a-zA-Z0-9_]+",str(code)) else "probe_http_error"
            print("Collector probe: "+safe,flush=True)
            if attempt==2:raise RuntimeError(safe) from None
            time.sleep(30)
    if not state.get("subscription_verified_at"):raise RuntimeError("Night subscription was not verified")
    print(json.dumps({"collector":url,"code":state.get("code"),"status":state.get("status"),
        "subscription_verified_at":state["subscription_verified_at"],"observations":len(state.get("history",[]))},ensure_ascii=False))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("Collector deployment/probe failed: "+type(exc).__name__)
        sys.exit(1)
