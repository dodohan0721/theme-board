#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 9차 — 회원 전용 상세 (첫 화면 공개 / 눌러야 나오는 정보는 로그인)

고객 요청
    "첫 화면에 보이는 내용까지만 공개하고, 거기서 눌러서 보는 세부 정보는
     결제한 회원만 볼 수 있게. 가입은 일단 이메일로."

무엇이 바뀌나
    web/data.json        공개  테마 카드 · 종목 시세 · 랭킹 · 카드 대표 문장
    web/priv/detail.json 회원  상승 사유 근거 기사 · 재무 8지표 · 관련 뉴스

    지금까지는 이 둘이 한 파일이라, 화면만 가려도 주소를 직접 치면
    전부 내려받을 수 있었습니다. 파일을 쪼개고, 회원용 파일 앞에
    Cloudflare 함수를 세워 로그인·승인 여부를 확인한 뒤에만 내어줍니다.

로그인 방식
    이메일 입력 → 6자리 인증번호 메일 → 확인 → 30일 유지
    인증번호와 로그인 증표는 모두 서명(HMAC)으로 만들어 검증하므로
    데이터베이스가 필요 없습니다. 비밀번호를 보관하지 않아 유출 위험도 없습니다.

    cd ~/theme-board
    python3 fix9.py
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []


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


def put(path, body, desc):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == body:
        SKIP.append(f"{desc} — 이미 같은 내용"); return
    open(path, "w", encoding="utf-8").write(body)
    OK.append(desc)


EX = "export_snapshot.py"
IX = "web/index.html"
for p in (EX, IX):
    if not os.path.exists(p):
        print(f"  {R}✗{N} {p} 없음 — ~/theme-board 에서 실행하세요."); sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════
# 1. 스냅샷을 공개용 / 회원용 두 파일로 나눈다
# ══════════════════════════════════════════════════════════════════════════
sub(EX, "스냅샷 분리 저장",
"""    out = {
        "ts": d["ts"], "themes": d["themes"], "stocks": d["stocks"], "ranking": d["ranking"],
        "universe": d["universe"], "scanned": d["scanned"], "theme_total": d["theme_total"],
        "details": details, "theme_stocks": theme_stocks,
        "generated_by": "export_snapshot.py",
    }
    p = os.path.join(WEB, "data.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(p) / 1024
""",
'''    # ── 공개용 / 회원용 분리 ───────────────────────────────────────────
    # 첫 화면(테마 카드·랭킹)에 필요한 것만 data.json 으로 내보내고,
    # 눌러야 나오는 상세(근거 기사·재무·뉴스)는 priv/detail.json 으로 뺀다.
    # priv/ 는 Cloudflare 함수가 로그인·승인을 확인한 뒤에만 내어준다.
    # 카드에 한 줄 걸리는 대표 문장(headline)만 공개 쪽에 남긴다.
    heads = {c: v["reason"]["headline"]
             for c, v in details.items()
             if (v.get("reason") or {}).get("headline")}

    out = {
        "ts": d["ts"], "themes": d["themes"], "stocks": d["stocks"], "ranking": d["ranking"],
        "universe": d["universe"], "scanned": d["scanned"], "theme_total": d["theme_total"],
        "heads": heads, "detail_codes": sorted(details.keys()),
        "theme_stocks": theme_stocks,
        "generated_by": "export_snapshot.py",
    }
    p = os.path.join(WEB, "data.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(p) / 1024

    pdir = os.path.join(WEB, "priv")
    os.makedirs(pdir, exist_ok=True)
    pp = os.path.join(pdir, "detail.json")
    json.dump({"ts": d["ts"], "details": details},
              open(pp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb2 = os.path.getsize(pp) / 1024
''',
    'heads = {c: v["reason"]["headline"]')

sub(EX, "저장 결과 출력",
'''    print(f" 완료 → web/data.json  ({kb:,.0f} KB)")''',
'''    print(f" 완료 → web/data.json      공개  ({kb:,.0f} KB)")
    print(f"        web/priv/detail.json 회원  ({kb2:,.0f} KB)")''',
    "web/priv/detail.json 회원")

# ══════════════════════════════════════════════════════════════════════════
# 2. Cloudflare 함수 — 로그인 · 승인 확인
# ══════════════════════════════════════════════════════════════════════════
LIB = r'''// 공통 — 서명(HMAC-SHA256)만으로 인증번호와 로그인 증표를 만든다.
// 데이터베이스가 없어도 되고, 비밀번호를 보관하지 않는다.

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

// ── 승인(결제) 여부 ───────────────────────────────────────────────────────
// MEMBERS 환경변수에 승인된 이메일을 쉼표로 적어 둔다.  "*" 이면 전원 허용.
// 결제 시스템을 붙이면 이 함수 하나만 바꾸면 된다.
export function isMember(env, email) {
  const raw = (env.MEMBERS || "").trim();
  if (!raw) return false;
  if (raw === "*") return true;
  return raw.split(",").map((x) => norm(x)).filter(Boolean).includes(norm(email));
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
'''

MID = r'''import { verifyToken, isMember, cookie, json } from "./_lib.js";

// 회원 전용 파일(priv/) 앞을 지키는 문지기.
// 로그인 안 했으면 401, 로그인은 했지만 승인 전이면 402 를 돌려준다.
// 통과하면 next() 가 원래 파일을 그대로 내어준다.
export async function onRequest(ctx) {
  const { request, env, next } = ctx;
  const path = new URL(request.url).pathname;

  if (!path.startsWith("/priv/")) return next();

  if (!env.AUTH_SECRET) return json({ error: "server_setup" }, 500);

  const s = await verifyToken(env.AUTH_SECRET, cookie(request, "tb_s"));
  if (!s) return json({ error: "login_required" }, 401);
  if (!isMember(env, s.email)) {
    return json({ error: "payment_required", email: s.email,
                  pay_url: env.PAY_URL || "" }, 402);
  }

  const res = await next();
  const out = new Response(res.body, res);
  out.headers.set("Cache-Control", "private, max-age=60");
  return out;
}
'''

LOGIN = r'''import { codeFor, norm, validEmail, isMember, json, need, SLOT_MS } from "../_lib.js";

// 이메일로 6자리 인증번호를 보낸다.
// 메일 발송은 Resend 를 쓴다(무료 월 3,000통). 키가 없으면 발송을 건너뛰고,
// DEV_SHOW_CODE=1 일 때만 화면에 번호를 띄워 준다(도메인 붙이기 전 시험용).
// 이때도 MEMBERS 에 이미 등록된 이메일에만 보여 준다.
// 그렇지 않으면 아무나 남의 주소를 넣고 번호를 받아 갈 수 있다.
export async function onRequestPost({ request, env }) {
  const bad = need(env); if (bad) return bad;

  let body = {};
  try { body = await request.json(); } catch (e) {}
  const email = norm(body.email);
  if (!validEmail(email)) return json({ error: "bad_email" }, 400);

  const code = await codeFor(env.AUTH_SECRET, email, Math.floor(Date.now() / SLOT_MS));

  if (env.RESEND_API_KEY && env.MAIL_FROM) {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: env.MAIL_FROM,
        to: [email],
        subject: "테마보드 인증번호",
        text: `인증번호 ${code}\n\n화면에 그대로 입력해 주세요. 5분 동안 사용할 수 있습니다.\n본인이 요청하지 않았다면 이 메일은 무시하셔도 됩니다.`,
      }),
    });
    if (!r.ok) {
      return json({ error: "mail_failed", msg: `메일 발송 실패 (${r.status})` }, 502);
    }
    return json({ ok: true, sent: true });
  }

  const dev = env.DEV_SHOW_CODE === "1" && isMember(env, email);
  return json({
    ok: true, sent: false,
    dev_code: dev ? code : undefined,
    msg: dev
      ? "시험 모드입니다. 아래 번호를 그대로 입력하세요."
      : "메일 발송이 아직 설정되지 않았습니다. 관리자에게 문의해 주세요.",
  });
}
'''

VERIFY = r'''import { codeFor, issue, norm, validEmail, isMember, json, need, SLOT_MS } from "../_lib.js";

// 인증번호를 확인하고 로그인 증표를 쿠키로 심는다.
// 직전 시간칸도 인정하므로 실제 유효시간은 5~10분이다.
export async function onRequestPost({ request, env }) {
  const bad = need(env); if (bad) return bad;

  let body = {};
  try { body = await request.json(); } catch (e) {}
  const email = norm(body.email);
  const code = String(body.code || "").replace(/\D/g, "");
  if (!validEmail(email)) return json({ error: "bad_email" }, 400);
  if (code.length !== 6) return json({ error: "bad_code" }, 400);

  const now = Math.floor(Date.now() / SLOT_MS);
  const a = await codeFor(env.AUTH_SECRET, email, now);
  const b = await codeFor(env.AUTH_SECRET, email, now - 1);
  if (code !== a && code !== b) return json({ error: "wrong_code" }, 401);

  const tok = await issue(env.AUTH_SECRET, email, 30);
  return json(
    { ok: true, email, paid: isMember(env, email), pay_url: env.PAY_URL || "" },
    200,
    { "Set-Cookie": `tb_s=${tok}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000` }
  );
}
'''

ME = r'''import { verifyToken, isMember, cookie, json } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  if (!env.AUTH_SECRET) return json({ error: "server_setup" }, 500);
  const s = await verifyToken(env.AUTH_SECRET, cookie(request, "tb_s"));
  if (!s) return json({ email: null, paid: false, pay_url: env.PAY_URL || "" });
  return json({ email: s.email, paid: isMember(env, s.email), pay_url: env.PAY_URL || "" });
}
'''

LOGOUT = r'''import { json } from "../_lib.js";

export async function onRequestPost() {
  return json({ ok: true }, 200,
    { "Set-Cookie": "tb_s=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0" });
}
'''

put("functions/_lib.js",          LIB,    "함수 공통 모듈")
put("functions/_middleware.js",   MID,    "회원 전용 파일 문지기")
put("functions/api/login.js",     LOGIN,  "인증번호 발송")
put("functions/api/verify.js",    VERIFY, "인증번호 확인 · 로그인")
put("functions/api/me.js",        ME,     "로그인 상태 조회")
put("functions/api/logout.js",    LOGOUT, "로그아웃")

# Cloudflare 가 함수로 넘길 주소만 지정 — 나머지는 정적 파일로 바로 나간다(빠르고 무료)
put("web/_routes.json",
    json.dumps({"version": 1, "include": ["/api/*", "/priv/*"], "exclude": []},
               ensure_ascii=False, indent=2) + "\n",
    "함수 적용 경로 지정")

# ══════════════════════════════════════════════════════════════════════════
# 3. 화면 — 첫 화면은 그대로, 상세만 잠근다
# ══════════════════════════════════════════════════════════════════════════
sub(IX, "회원 상태값",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap', compact=false, dedup=true, dupN=0;",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap', compact=false, dedup=true, dupN=0;\n"
    "let DETAIL=null, ME=null;",
    "let DETAIL=null, ME=null;")

sub(IX, "카드 대표 문장을 공개본에서 읽기",
"""function themeHead(t){
  const DT=RAW.details||{};
  for(const c of (t.codes||[])){
    const r=(DT[c]||{}).reason;
    if(r&&r.status==='ok'&&r.headline)
      return {code:c, name:(RAW.stocks[c]||{}).name||'', headline:r.headline, verified:!!r.verified};
  }
  return null;
}""",
"""function themeHead(t){
  const H=RAW.heads||{};
  for(const c of (t.codes||[])){
    if(H[c]) return {code:c, name:(RAW.stocks[c]||{}).name||'', headline:H[c], verified:true};
  }
  return null;
}""",
    "const H=RAW.heads||{};")

sub(IX, "로그인 버튼",
"""  <div class="stat"><span class="dot" id="dot"></span><span id="stat">불러오는 중…</span></div>""",
"""  <button id="authbtn" onclick="openAuth()" style="padding:7px 13px;border-radius:8px;font-size:13.5px;font-weight:800;border:1px solid #d8dee4;background:#fff;color:#333;cursor:pointer;margin-left:8px">로그인</button>
  <div class="stat"><span class="dot" id="dot"></span><span id="stat">불러오는 중…</span></div>""",
    'id="authbtn"')

sub(IX, "화면 열 때 로그인 상태 확인",
"""    RAW=await r.json(); applyFilter();""",
"""    RAW=await r.json(); applyFilter(); checkMe();""",
    "applyFilter(); checkMe();")

AUTHJS = """
// ── 회원 전용 상세 ───────────────────────────────────────────────────────
// 첫 화면(테마 카드 · 종목 시세 · 랭킹 · 대표 문장)은 누구나 볼 수 있다.
// 종목을 눌렀을 때 나오는 상세(상승 사유 근거 · 재무 · 뉴스)만 회원에게 열린다.
// 데이터 자체가 다른 파일(priv/detail.json)로 나뉘어 있고 서버가 지키므로,
// 화면만 가린 것이 아니라 실제로 내려받을 수 없다.
async function checkMe(){
  try{ const r=await fetch('/api/me'); ME=await r.json(); }catch(e){ ME=null; }
  const b=$('authbtn'); if(!b) return;
  if(ME&&ME.email) b.textContent = ME.paid ? '회원 ✓' : '승인 대기';
  else b.textContent = '로그인';
}
async function needDetail(){
  if(DETAIL) return true;
  let r;
  try{ r=await fetch('priv/detail.json?t='+Date.now()); }
  catch(e){ lockSheet('상세를 불러오지 못했습니다', e.message); return false; }
  if(r.status===401){ openAuth(); return false; }
  if(r.status===402){ let j={}; try{ j=await r.json(); }catch(e){} payWall(j); return false; }
  if(!r.ok){ lockSheet('상세를 불러오지 못했습니다', 'HTTP '+r.status); return false; }
  const j=await r.json(); DETAIL=j.details||j; return true;
}
function lockSheet(title, msg){
  openDt(`<div class="dhead"><div style="font-size:20px;font-weight:900">${title}</div>
    <button class="x" onclick="closeDt()">✕</button></div>
    <div class="dbody"><div class="blk"><p>${msg||''}</p></div></div>`);
}
function payWall(j){
  const u=(j&&j.pay_url)||'';
  openDt(`<div class="dhead"><div style="font-size:20px;font-weight:900">회원 전용 정보입니다</div>
    <button class="x" onclick="closeDt()">✕</button></div>
  <div class="dbody"><div class="blk" style="border-left:3px solid var(--teal)">
    <h4>🔒 상세는 결제 후 열립니다</h4>
    <p><b>${(j&&j.email)||''}</b> 으로 로그인되어 있습니다.<br>
       테마·거래대금·등락률·랭킹은 지금처럼 계속 보실 수 있고,<br>
       종목을 눌렀을 때 나오는 <b>상승 사유 근거 기사 · 재무 8지표 · 관련 뉴스</b>는 회원에게만 열립니다.</p>
    ${u?`<p style="margin-top:14px"><a href="${u}" target="_blank" rel="noopener"
       style="display:inline-block;padding:12px 20px;border-radius:10px;background:var(--teal-d,#04868c);color:#fff;font-weight:800;text-decoration:none">결제하고 이용하기 →</a></p>`
      :`<div class="disc">결제 페이지가 아직 연결되지 않았습니다. 관리자 승인 후 바로 열립니다.</div>`}
  </div></div>`);
}
function openAuth(){
  openDt(`<div class="dhead"><div style="font-size:20px;font-weight:900">이메일로 로그인</div>
    <button class="x" onclick="closeDt()">✕</button></div>
  <div class="dbody"><div class="blk">
    <p>테마·거래대금·등락률·랭킹은 <b>로그인 없이</b> 보실 수 있습니다.<br>
       종목을 눌렀을 때 나오는 <b>상승 사유 근거 기사 · 재무 · 뉴스</b>만 회원에게 열립니다.</p>
    <div style="display:flex;gap:8px;margin:14px 0 0">
      <input id="au_em" type="email" autocomplete="email" placeholder="name@example.com"
             style="flex:1;padding:11px 12px;border:1px solid #d8dee4;border-radius:9px;font-size:15px">
      <button id="au_b1" onclick="sendCode()"
             style="padding:11px 16px;border:0;border-radius:9px;background:var(--teal-d,#04868c);color:#fff;font-weight:800;cursor:pointer;white-space:nowrap">인증번호 받기</button>
    </div>
    <div id="au_s2" style="display:none;margin-top:10px">
      <div style="display:flex;gap:8px">
        <input id="au_cd" inputmode="numeric" maxlength="6" placeholder="6자리 숫자"
             style="flex:1;padding:11px 12px;border:1px solid #d8dee4;border-radius:9px;font-size:15px;letter-spacing:4px">
        <button onclick="verifyCode()"
             style="padding:11px 22px;border:0;border-radius:9px;background:#111;color:#fff;font-weight:800;cursor:pointer">확인</button>
      </div>
      <div class="disc">인증번호는 <b>5분</b> 동안 쓸 수 있습니다. 메일이 안 오면 스팸함도 확인해 주세요.</div>
    </div>
    <div id="au_msg" style="margin-top:12px;font-size:13.5px;color:var(--ink2);white-space:pre-line"></div>
    ${ME&&ME.email?`<div class="disc">현재 <b>${ME.email}</b> 로 로그인되어 있습니다.
      <a href="#" onclick="doLogout();return false;" style="color:var(--teal-d,#04868c);font-weight:800">로그아웃</a></div>`:''}
  </div></div>`);
  setTimeout(()=>{const e=$('au_em'); if(e){ if(ME&&ME.email)e.value=ME.email; e.focus(); }},60);
}
function auMsg(t,bad){ const m=$('au_msg'); if(m){ m.textContent=t; m.style.color=bad?'#b42318':'var(--ink2)'; } }
async function sendCode(){
  const em=($('au_em').value||'').trim();
  if(!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/.test(em)){ auMsg('이메일 주소를 다시 확인해 주세요.',1); return; }
  const b=$('au_b1'); b.disabled=true; b.textContent='보내는 중…'; auMsg('');
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
                                     body:JSON.stringify({email:em})});
    const j=await r.json();
    if(!r.ok){ auMsg(j.msg||'발송에 실패했습니다. 잠시 후 다시 시도해 주세요.',1); }
    else{
      $('au_s2').style.display='block';
      if(j.dev_code) auMsg('시험 모드 — 인증번호 '+j.dev_code);
      else auMsg(j.sent?(em+' 으로 인증번호를 보냈습니다.'):(j.msg||''), !j.sent);
      const c=$('au_cd'); if(c)c.focus();
    }
  }catch(e){ auMsg('네트워크 오류: '+e.message,1); }
  b.disabled=false; b.textContent='인증번호 받기';
}
async function verifyCode(){
  const em=($('au_em').value||'').trim(), cd=($('au_cd').value||'').replace(/\\D/g,'');
  if(cd.length!==6){ auMsg('6자리 숫자를 입력해 주세요.',1); return; }
  try{
    const r=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},
                                      body:JSON.stringify({email:em,code:cd})});
    const j=await r.json();
    if(!r.ok){ auMsg('인증번호가 맞지 않거나 시간이 지났습니다. 다시 받아 주세요.',1); return; }
    ME=j; DETAIL=null; checkMe();
    if(j.paid){ closeDt(); }
    else payWall(j);
  }catch(e){ auMsg('네트워크 오류: '+e.message,1); }
}
async function doLogout(){
  try{ await fetch('/api/logout',{method:'POST'}); }catch(e){}
  ME=null; DETAIL=null; checkMe(); closeDt();
}
"""

sub(IX, "로그인 화면 · 상세 잠금",
    "function openStock(code){\n  const s=D.stocks[code], j=(D.details||{})[code];",
    AUTHJS + "\nasync function openStock(code){\n  const s=D.stocks[code];\n"
             "  if(!await needDetail()) return;\n  const j=(DETAIL||{})[code];",
    "async function needDetail(){")

# ══════════════════════════════════════════════════════════════════════════
# 4. 검사
# ══════════════════════════════════════════════════════════════════════════
import py_compile
try:
    py_compile.compile(EX, doraise=True); OK.append("export_snapshot.py 문법 정상")
except Exception as e:
    FAIL.append(f"export_snapshot.py 문법 오류: {e}")

h = open(IX, encoding="utf-8").read()
if h.count("`") % 2 == 0: OK.append("템플릿 문자열 짝 정상")
else: FAIL.append("백틱(`) 홀수 — 템플릿 문자열 깨짐")
if "D.details" in h: FAIL.append("index.html 에 옛 D.details 참조가 남아 있음")

print("\n" + "=" * 62)
for x in OK:   print(f"  {G}✓{N} {x}")
for x in SKIP: print(f"  {Y}·{N} {x}")
for x in FAIL: print(f"  {R}✗{N} {x}")
print("=" * 62)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)

print(f"""
{B}1) Cloudflare 에 환경변수 4개를 넣습니다{N}

  dash.cloudflare.com → Workers & Pages → theme-board
    → Settings → Variables and Secrets → Add

    AUTH_SECRET     아래 명령으로 만든 긴 문자열 (절대 공개 금지)
    MEMBERS         승인할 이메일을 쉼표로.  예)  a@b.com,c@d.com
                    시험 중에는  *  하나만 넣으면 로그인한 사람 전원 허용
    DEV_SHOW_CODE   1   ← 메일 발송 붙이기 전, 화면에 인증번호를 띄우는 시험 모드
    PAY_URL         (선택) 결제 페이지 주소. 없으면 '관리자 승인 후 열림'으로 안내

  AUTH_SECRET 만들기:
    python3 -c "import secrets;print(secrets.token_urlsafe(48))"

{B}2) 메일 발송 (도메인 연결 후){N}

  resend.com 가입 → 도메인 인증 → API 키 발급, 환경변수 2개 추가
    RESEND_API_KEY  re_...
    MAIL_FROM       테마보드 <no-reply@내도메인>
  그리고 DEV_SHOW_CODE 는 지웁니다.

{B}3) 반영{N}
    git add -A
    git commit -m "회원 전용 상세 — 첫 화면 공개, 상세는 로그인·승인 후"
    git push
    python3 export_snapshot.py --cycles 2 --detail 60 --ai --ai-top 30
    npx wrangler pages deploy web --project-name theme-board --branch main --commit-dirty=true

{B}4) 확인{N}
    https://theme-board.pages.dev/priv/detail.json   →  401 이 떠야 정상
    첫 화면의 테마 카드·랭킹은 그대로 보이고,
    종목을 누르면 로그인 창이 뜨면 성공입니다.
""")
