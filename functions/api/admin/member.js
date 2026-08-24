import { requireAdmin, getMember, saveMember, norm, validEmail, MKEY, json }
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
