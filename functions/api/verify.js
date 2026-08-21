import { codeFor, issue, norm, validEmail, isMember, json, need, SLOT_MS } from "../_lib.js";

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
