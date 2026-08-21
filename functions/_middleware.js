import { verifyToken, isMember, cookie, json } from "./_lib.js";

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
