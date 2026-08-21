import { json } from "../_lib.js";

export async function onRequestPost() {
  return json({ ok: true }, 200,
    { "Set-Cookie": "tb_s=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0" });
}
