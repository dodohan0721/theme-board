import { codeFor, norm, validEmail, isMember, json, need, SLOT_MS } from "../_lib.js";

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
