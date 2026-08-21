import { verifyToken, isMember, cookie, json } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  if (!env.AUTH_SECRET) return json({ error: "server_setup" }, 500);
  const s = await verifyToken(env.AUTH_SECRET, cookie(request, "tb_s"));
  if (!s) return json({ email: null, paid: false, pay_url: env.PAY_URL || "" });
  return json({ email: s.email, paid: isMember(env, s.email), pay_url: env.PAY_URL || "" });
}
