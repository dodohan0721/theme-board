import {nightResponse} from "./_night.js";
export async function onRequestGet({env}) { return nightResponse(env); }
