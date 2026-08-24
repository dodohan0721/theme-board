// 공통 — 서명(HMAC-SHA256)으로 인증번호와 로그인 증표를 만들고,
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
