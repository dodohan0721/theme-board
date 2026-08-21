// 공통 — 서명(HMAC-SHA256)만으로 인증번호와 로그인 증표를 만든다.
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
