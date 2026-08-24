import { requireAdmin, json } from "../../_lib.js";

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
