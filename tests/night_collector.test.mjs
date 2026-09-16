import test from "node:test";
import assert from "node:assert/strict";
import {session,isOpen,chooseCode,parseTick,mergeTick,publicState} from "../collectors/night/worker.mjs";
const at=s=>Date.parse(s+"+09:00");
const raw=(code,time,last,sign="2")=>"0|H0MFCNT0|001|"+[code,time,"2.5",sign,"0.5",last,"1000","1050","980","1","500","4000"].concat(Array(37).fill("0")).join("^");
test("Korean session boundaries and weekends",()=>{
 assert.equal(isOpen(at("2026-09-16T18:00:00")),true);
 assert.equal(isOpen(at("2026-09-17T05:59:59")),true);
 assert.equal(isOpen(at("2026-09-17T06:00:00")),false);
 assert.equal(isOpen(at("2026-09-19T05:00:00")),true);
 assert.equal(isOpen(at("2026-09-19T18:00:00")),false);
 assert.equal(session(at("2026-09-17T01:00:00")),"2026-09-16");
});
test("choose standard contract even if mini volume is larger",()=>{
 assert.equal(chooseCode([{futs_shrn_iscd:"A05610",hts_kor_isnm:"미니F",acml_vol:5000},{futs_shrn_iscd:"A01612",hts_kor_isnm:"F 202612",acml_vol:100}]).code,"A01612");
 assert.throws(()=>chooseCode([{futs_shrn_iscd:"A05610",hts_kor_isnm:"미니F"}]));
});
test("reject day/stale/wrong symbol/bad prices and handle midnight",()=>{
 const now=at("2026-09-16T23:59:59");
 const tick=parseTick(raw("A01612","235958","1040","5"),"A01612",now);
 assert.equal(tick.ts,"2026-09-16 23:59:58");assert.equal(tick.rate,-0.5);
 for(const [code,hour,price] of [["A05610","235958",1040],["A01612","153000",1040],["A01612","230000",1040],["A01612","235959","NaN"]])assert.equal(parseTick(raw(code,hour,price),"A01612",now),null);
 assert.equal(parseTick(raw("A01612","235959","1040"),"A01612",at("2026-09-17T00:00:01")).ts,"2026-09-16 23:59:59");
});
test("one value per minute; retain midnight; reset next session and contract",()=>{
 const make=(ts,value)=>({code:"A01612",ts:ts.replace("T"," "),observed_at:new Date(at(ts)).toISOString(),last:value});
 let d=mergeTick(null,make("2026-09-16T23:59:10",1000));
 d=mergeTick(d,make("2026-09-16T23:59:45",1001));d=mergeTick(d,make("2026-09-17T00:00:15",1002));
 assert.equal(d.history.length,2);assert.equal(d.history[0].last,1001);
 assert.equal(mergeTick(d,make("2026-09-17T18:00:05",1003)).history.length,1);
 assert.equal(mergeTick(d,{...make("2026-09-17T00:01:05",1003),code:"A01703"}).history.length,1);
});
test("stale, closed and failed data never claims live",()=>{
 const d={last:1000,observed_at:"2026-09-16T09:00:00Z",history:[]};
 assert.equal(publicState(d,at("2026-09-16T18:02:00")).status,"receiving");
 assert.equal(publicState(d,at("2026-09-16T18:04:00")).status,"stale");
 assert.equal(publicState(d,at("2026-09-17T06:00:00")).status,"closed");
 assert.equal(publicState({history:[],last_error:"websocket_error"},at("2026-09-16T18:02:00")).status,"error");
});
