#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 11차 — 관리자 화면 (사장님이 직접 승인)

지금까지
    승인 명단이 Cloudflare 환경변수(MEMBERS)에 텍스트로 들어 있어서,
    한 명 승인하려면 대시보드에서 값을 고치고 사이트를 다시 올려야 했습니다.

이제부터
    사이트에 로그인하면 관리자에게만 [관리자] 버튼이 보입니다.
    이메일 인증을 마친 분들이 목록에 쌓이고, [승인] 을 누르면 즉시 열립니다.
    다시 배포할 필요가 없습니다.

저장은 Cloudflare KV 를 씁니다. 무료 한도(하루 읽기 10만 · 쓰기 1천) 안이라
운영비는 그대로입니다.

    cd ~/theme-board
    python3 fix11.py        # 코드만 반영
    bash setup11.sh         # KV 만들고 · 기존 명단 옮기고 · 배포까지
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []


def put(path, body, desc):
    d = os.path.dirname(path)
    if d: os.makedirs(d, exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == body:
        SKIP.append(f"{desc} — 이미 같은 내용"); return
    open(path, "w", encoding="utf-8").write(body)
    OK.append(desc)


def sub(path, desc, old, new, marker=None):
    if not os.path.exists(path):
        FAIL.append(f"{desc} — {path} 없음"); return
    s = open(path, encoding="utf-8").read()
    if (marker or new) in s:
        SKIP.append(f"{desc} — 이미 적용됨"); return
    if old not in s:
        FAIL.append(f"{desc} — 위치를 못 찾음"); return
    open(path, "w", encoding="utf-8").write(s.replace(old, new, 1))
    OK.append(desc)


for p in ("web/index.html", "functions/_lib.js", ".github/workflows/snapshot.yml"):
    if not os.path.exists(p):
        print(f"  {R}✗{N} {p} 없음 — fix9 를 먼저 적용하셨는지 확인해 주세요."); sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════
# 1. 공통 모듈 — 승인 여부를 KV 에서 읽는다
# ══════════════════════════════════════════════════════════════════════════
LIB = r'''// 공통 — 서명(HMAC-SHA256)으로 인증번호와 로그인 증표를 만들고,
// 승인 명단은 Cloudflare KV 에 둔다(관리자 화면에서 즉시 바꿀 수 있게).

const enc = new TextEncoder();

async function key(secret) {
  return crypto.subtle.importKey("raw", enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

export async function mac(secret, msg) {
  const sig = await crypto.subtle.sign("HMAC", await key(secret), enc.encode(msg));
  return new Uint8Array(sig);
}

export function b64u(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function eq(a, b) {           // 길이가 같은 문자열을 시간차 없이 비교
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export function norm(email) {
  return String(email || "").trim().toLowerCase();
}

export function validEmail(e) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(e) && e.length <= 254;
}

// ── 인증번호 ──────────────────────────────────────────────────────────────
// 5분짜리 시간칸(slot)을 정해 이메일과 함께 서명한다.
// 저장하지 않아도 같은 값이 다시 나오므로 검증이 된다.
export const SLOT_MS = 5 * 60 * 1000;

export async function codeFor(secret, email, slot) {
  const m = await mac(secret, `code|${email}|${slot}`);
  const n = ((m[0] << 24) | (m[1] << 16) | (m[2] << 8) | m[3]) >>> 0;
  return String(n % 1000000).padStart(6, "0");
}

// ── 로그인 증표 ───────────────────────────────────────────────────────────
export async function issue(secret, email, days) {
  const exp = Date.now() + (days || 30) * 86400000;
  const body = `${email}|${exp}`;
  return `${b64u(enc.encode(body))}.${b64u(await mac(secret, body))}`;
}

export async function verifyToken(secret, tok) {
  if (!tok || tok.indexOf(".") < 0) return null;
  const [p, s] = tok.split(".");
  let body;
  try {
    body = atob(p.replace(/-/g, "+").replace(/_/g, "/"));
  } catch (e) { return null; }
  const i = body.lastIndexOf("|");
  if (i < 0) return null;
  const email = body.slice(0, i), exp = Number(body.slice(i + 1));
  if (!exp || exp < Date.now()) return null;
  if (!eq(s, b64u(await mac(secret, body)))) return null;
  return { email, exp };
}

export function cookie(req, name) {
  const c = req.headers.get("Cookie") || "";
  for (const part of c.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

// ── 회원 명부 (KV) ────────────────────────────────────────────────────────
// 키   m:<이메일>
// 값   { email, status: "pending" | "approved", created, approved, seen }
export const MKEY = (email) => "m:" + norm(email);

export async function getMember(env, email) {
  if (!env.TB) return null;
  const v = await env.TB.get(MKEY(email));
  if (!v) return null;
  try { return JSON.parse(v); } catch (e) { return null; }
}

export async function saveMember(env, m) {
  if (!env.TB) return;
  await env.TB.put(MKEY(m.email), JSON.stringify(m));
}

// 인증을 마친 사람을 명부에 남긴다. 처음이면 '승인 대기'로.
export async function touchMember(env, email) {
  if (!env.TB) return null;
  const e = norm(email);
  const cur = await getMember(env, e);
  const now = Date.now();
  const m = cur
    ? { ...cur, seen: now }
    : { email: e, status: "pending", created: now, seen: now };
  await saveMember(env, m);
  return m;
}

// ── 승인 여부 ─────────────────────────────────────────────────────────────
// KV 가 먼저, 환경변수 MEMBERS 는 비상용 고정 명단으로 함께 인정한다.
// (KV 를 붙이기 전 설정이 그대로 살아 있게 하려는 것)
export async function isMember(env, email) {
  const e = norm(email);
  const raw = (env.MEMBERS || "").trim();
  if (raw === "*") return true;
  if (raw && raw.split(",").map(norm).filter(Boolean).includes(e)) return true;
  const m = await getMember(env, e);
  return !!m && m.status === "approved";
}

export function isAdmin(env, email) {
  const raw = (env.ADMINS || "").trim();
  if (!raw) return false;
  return raw.split(",").map(norm).filter(Boolean).includes(norm(email));
}

export function json(obj, status, extra) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: Object.assign(
      { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      extra || {}),
  });
}

export function need(env) {
  if (!env.AUTH_SECRET || env.AUTH_SECRET.length < 16) {
    return json({ error: "server_setup", msg: "AUTH_SECRET 환경변수가 없습니다." }, 500);
  }
  return null;
}

// 관리자 요청인지 확인하고, 아니면 오류 응답을 돌려준다.
export async function requireAdmin(request, env) {
  const bad = need(env); if (bad) return { err: bad };
  const s = await verifyToken(env.AUTH_SECRET, cookie(request, "tb_s"));
  if (!s) return { err: json({ error: "login_required" }, 401) };
  if (!isAdmin(env, s.email)) return { err: json({ error: "forbidden" }, 403) };
  if (!env.TB) return { err: json({ error: "kv_missing",
    msg: "회원 명부 저장소(KV)가 연결되지 않았습니다. setup11.sh 를 실행해 주세요." }, 500) };
  return { email: s.email };
}
'''
put("functions/_lib.js", LIB, "공통 모듈 — KV 명부 · 관리자 판정")

# ── isMember 가 async 가 되었으므로 부르는 쪽을 모두 await ────────────────
sub("functions/_middleware.js", "문지기 — 승인 확인을 await 로",
    "  if (!isMember(env, s.email)) {",
    "  if (!(await isMember(env, s.email))) {",
    "await isMember(env, s.email)")

sub("functions/api/login.js", "인증번호 발송 — 승인 확인을 await 로",
    '  const dev = env.DEV_SHOW_CODE === "1" && isMember(env, email);',
    '  const dev = env.DEV_SHOW_CODE === "1" && (await isMember(env, email));',
    "await isMember(env, email)")

sub("functions/api/me.js", "로그인 상태 조회 — 승인 확인 · 관리자 여부",
    '  return json({ email: s.email, paid: isMember(env, s.email), pay_url: env.PAY_URL || "" });',
    '  return json({ email: s.email, paid: await isMember(env, s.email),\n'
    '                admin: isAdmin(env, s.email), pay_url: env.PAY_URL || "" });',
    "admin: isAdmin(env, s.email)")

sub("functions/api/me.js", "로그인 상태 조회 — 모듈 불러오기",
    'import { verifyToken, isMember, cookie, json } from "../_lib.js";',
    'import { verifyToken, isMember, isAdmin, cookie, json } from "../_lib.js";',
    "isMember, isAdmin, cookie")

sub("functions/api/verify.js", "인증 확인 — 모듈 불러오기",
    'import { codeFor, issue, norm, validEmail, isMember, json, need, SLOT_MS } from "../_lib.js";',
    'import { codeFor, issue, norm, validEmail, isMember, isAdmin, touchMember,\n'
    '         json, need, SLOT_MS } from "../_lib.js";',
    "touchMember,")

sub("functions/api/verify.js", "인증 확인 — 명부에 남기고 승인 여부 확인",
    """  const tok = await issue(env.AUTH_SECRET, email, 30);
  return json(
    { ok: true, email, paid: isMember(env, email), pay_url: env.PAY_URL || "" },""",
    """  // 인증을 마친 사람을 명부에 남긴다(처음이면 '승인 대기').
  await touchMember(env, email);

  const tok = await issue(env.AUTH_SECRET, email, 30);
  return json(
    { ok: true, email, paid: await isMember(env, email),
      admin: isAdmin(env, email), pay_url: env.PAY_URL || "" },""",
    "await touchMember(env, email);")

# ══════════════════════════════════════════════════════════════════════════
# 2. 관리자 API
# ══════════════════════════════════════════════════════════════════════════
MEMBERS_API = r'''import { requireAdmin, json } from "../../_lib.js";

// 명부 전체를 돌려준다. 승인 대기가 위로 오게 정렬한다.
export async function onRequestGet({ request, env }) {
  const a = await requireAdmin(request, env);
  if (a.err) return a.err;

  const out = [];
  let cursor;
  do {
    const r = await env.TB.list({ prefix: "m:", cursor, limit: 1000 });
    for (const k of r.keys) {
      const v = await env.TB.get(k.name);
      if (!v) continue;
      try { out.push(JSON.parse(v)); } catch (e) {}
    }
    cursor = r.list_complete ? null : r.cursor;
  } while (cursor);

  const rank = (m) => (m.status === "approved" ? 1 : 0);
  out.sort((x, y) => rank(x) - rank(y) || (y.seen || 0) - (x.seen || 0));

  return json({
    ok: true,
    me: a.email,
    fixed: (env.MEMBERS || "").trim(),   // 환경변수 고정 명단(참고용)
    members: out,
  });
}
'''

MEMBER_API = r'''import { requireAdmin, getMember, saveMember, norm, validEmail, MKEY, json }
  from "../../_lib.js";

// 한 사람의 상태를 바꾼다.  action: approve | revoke | remove
export async function onRequestPost({ request, env }) {
  const a = await requireAdmin(request, env);
  if (a.err) return a.err;

  let body = {};
  try { body = await request.json(); } catch (e) {}
  const email = norm(body.email);
  const action = String(body.action || "");
  if (!validEmail(email)) return json({ error: "bad_email" }, 400);

  if (action === "remove") {
    await env.TB.delete(MKEY(email));
    return json({ ok: true, removed: email });
  }
  if (action !== "approve" && action !== "revoke") {
    return json({ error: "bad_action" }, 400);
  }

  const now = Date.now();
  const cur = (await getMember(env, email)) || { email, created: now };
  const m = {
    ...cur,
    email,
    status: action === "approve" ? "approved" : "pending",
    approved: action === "approve" ? now : null,
  };
  await saveMember(env, m);
  return json({ ok: true, member: m });
}
'''
put("functions/api/admin/members.js", MEMBERS_API, "관리자 API — 명부 조회")
put("functions/api/admin/member.js",  MEMBER_API,  "관리자 API — 승인 · 해제 · 삭제")

# ══════════════════════════════════════════════════════════════════════════
# 3. 배포 설정 — KV 를 붙이려면 wrangler.toml 이 필요하다
# ══════════════════════════════════════════════════════════════════════════
TOML = '''# Cloudflare Pages 설정
#
# KV(회원 명부)를 붙이기 위한 파일입니다.
# id 는 setup11.sh 가 KV 를 만들면서 채워 넣습니다.
#
# ※ 이 파일이 있으면 배포할 때 폴더를 따로 적지 않습니다.
#      npx wrangler pages deploy          (O)
#      npx wrangler pages deploy web      (X — 오류)

name = "theme-board"
pages_build_output_dir = "web"
compatibility_date = "2026-08-01"

[[kv_namespaces]]
binding = "TB"
id = "KV_ID_HERE"
'''
put("wrangler.toml", TOML, "배포 설정 파일(wrangler.toml)")

sub(".github/workflows/snapshot.yml", "자동 갱신 — 배포 명령에서 폴더 인자 제거",
    "            npx --yes wrangler@latest pages deploy web \\\n"
    "              --project-name theme-board --branch main --commit-dirty=true \\",
    "            npx --yes wrangler@latest pages deploy \\\n"
    "              --project-name theme-board --branch main --commit-dirty=true \\",
    "wrangler@latest pages deploy \\")

# ══════════════════════════════════════════════════════════════════════════
# 4. 화면 — 관리자 메뉴
# ══════════════════════════════════════════════════════════════════════════
sub("web/index.html", "관리자 버튼",
    """  <button id="authbtn" onclick="openAuth()" style="padding:7px 13px;border-radius:8px;font-size:13.5px;font-weight:800;border:1px solid #d8dee4;background:#fff;color:#333;cursor:pointer;margin-left:8px">로그인</button>""",
    """  <button id="adminbtn" onclick="openAdmin()" style="display:none;padding:7px 13px;border-radius:8px;font-size:13.5px;font-weight:800;border:1px solid var(--teal);background:#eefafa;color:var(--teal-d,#04868c);cursor:pointer;margin-left:8px">관리자</button>
  <button id="authbtn" onclick="openAuth()" style="padding:7px 13px;border-radius:8px;font-size:13.5px;font-weight:800;border:1px solid #d8dee4;background:#fff;color:#333;cursor:pointer;margin-left:8px">로그인</button>""",
    'id="adminbtn"')

sub("web/index.html", "관리자 버튼 표시 조건",
    """  if(ME&&ME.email) b.textContent = ME.paid ? '회원 ✓' : '승인 대기';
  else b.textContent = '로그인';""",
    """  if(ME&&ME.email) b.textContent = ME.paid ? '회원 ✓' : '승인 대기';
  else b.textContent = '로그인';
  const ab=$('adminbtn'); if(ab) ab.style.display = (ME&&ME.admin) ? '' : 'none';""",
    "ME&&ME.admin) ? '' : 'none'")

ADMINJS = """
// ── 관리자 화면 ──────────────────────────────────────────────────────────
// 이메일 인증을 마친 사람이 명부에 쌓인다. [승인] 을 누르면 그 즉시 열린다.
// 다시 배포할 필요가 없다 — 명부가 코드가 아니라 저장소에 있기 때문이다.
function dfmt(t){ if(!t) return '-'; const d=new Date(t);
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`; }
async function openAdmin(){
  openDt(`<div class="dhead"><div style="font-size:20px;font-weight:900">회원 관리</div>
    <button class="x" onclick="closeDt()">✕</button></div>
    <div class="dbody"><div class="blk"><p id="ad_body">불러오는 중…</p></div></div>`);
  loadAdmin();
}
async function loadAdmin(){
  let j;
  try{ const r=await fetch('/api/admin/members?t='+Date.now()); j=await r.json();
       if(!r.ok) throw new Error(j.msg||j.error||('HTTP '+r.status)); }
  catch(e){ const b=$('ad_body'); if(b) b.innerHTML=`<span style="color:#b42318">${e.message}</span>`; return; }
  const ms=j.members||[];
  const wait=ms.filter(m=>m.status!=='approved'), ok=ms.filter(m=>m.status==='approved');
  // 표 대신 가로 배치 — 좁은 화면에서도 버튼이 잘리지 않는다
  const bs='padding:5px 10px;border-radius:7px;font-weight:800;cursor:pointer;font-size:12.5px';
  const row=m=>`<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--line)">
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;word-break:break-all;font-size:13.5px">${m.email}</div>
      <div style="color:var(--ink3);font-size:11.5px">가입 ${dfmt(m.created)} · 최근 ${dfmt(m.seen)}</div>
    </div>
    <div style="flex:none;white-space:nowrap">
      ${m.status==='approved'
        ? `<button onclick="setMember('${m.email}','revoke')" style="${bs};border:1px solid #d8dee4;background:#fff">해제</button>`
        : `<button onclick="setMember('${m.email}','approve')" style="${bs};border:0;background:var(--teal-d,#04868c);color:#fff">승인</button>`}
      <button onclick="setMember('${m.email}','remove')" title="명부에서 지우기" style="${bs};margin-left:4px;border:1px solid #f0d0cd;background:#fff;color:#b42318">삭제</button>
    </div></div>`;
  const tbl=(list,empty)=>list.length
    ? list.map(row).join('')
    : `<p style="color:var(--ink3);margin:4px 0 0">${empty}</p>`;
  $('ad_body').outerHTML=`
    <h4>승인 대기 ${wait.length}명</h4>
    ${tbl(wait,'대기 중인 분이 없습니다.')}
    <h4 style="margin-top:18px">승인됨 ${ok.length}명</h4>
    ${tbl(ok,'아직 없습니다.')}
    ${j.fixed?`<div class="disc">환경변수에 고정된 계정: <b>${j.fixed}</b><br>
      이 계정들은 명부와 상관없이 항상 열립니다. 비상용이라 이 화면에서는 못 바꿉니다.</div>`:''}
    <div class="disc">[승인] 을 누르면 <b>즉시 반영</b>됩니다. 다시 배포하지 않으셔도 됩니다.
      상대방이 이미 로그인해 계시면 새로고침만 하시면 열립니다.</div>`;
}
async function setMember(email, action){
  if(action==='remove' && !confirm(email+' 을 명부에서 지울까요?')) return;
  try{
    const r=await fetch('/api/admin/member',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({email,action})});
    if(!r.ok){ const j=await r.json().catch(()=>({})); alert(j.msg||j.error||('HTTP '+r.status)); return; }
  }catch(e){ alert('네트워크 오류: '+e.message); return; }
  DETAIL=null; openAdmin();
}
"""
sub("web/index.html", "관리자 화면",
    "\n// ── 회원 전용 상세 ───────────────────────────────────────────────────────",
    ADMINJS + "\n// ── 회원 전용 상세 ───────────────────────────────────────────────────────",
    "async function loadAdmin(){")

# ══════════════════════════════════════════════════════════════════════════
# 5. 검사
# ══════════════════════════════════════════════════════════════════════════
h = open("web/index.html", encoding="utf-8").read()
if h.count("`") % 2 == 0: OK.append("템플릿 문자열 짝 정상")
else: FAIL.append("백틱(`) 홀수 — 템플릿 문자열 깨짐")

import re
for f in ["functions/_middleware.js", "functions/api/login.js",
          "functions/api/me.js", "functions/api/verify.js"]:
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r"(?<!await )(?<!async function )isMember\(", s):
        seg = s[max(0, m.start()-10):m.start()]
        if "await" not in seg and "import" not in s[:m.start()].split("\n")[-1]:
            FAIL.append(f"{f} — await 없는 isMember() 호출이 남아 있음")
            break
    else:
        OK.append(f"{f.split('/')[-1]} — isMember 호출 정상")

print("\n" + "=" * 62)
for x in OK:   print(f"  {G}✓{N} {x}")
for x in SKIP: print(f"  {Y}·{N} {x}")
for x in FAIL: print(f"  {R}✗{N} {x}")
print("=" * 62)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)

print(f"""
{B}다음{N}
    bash setup11.sh

  KV 를 만들고 · 기존 승인 명단을 옮기고 · 관리자를 지정하고 · 배포까지 합니다.
""")
