/* Pointer-driven glass lighting and small button feedback; leaves all click handlers intact. */
(() => {
 'use strict';
 const root=document.body;
 if(!root.classList.contains('rt-app'))return;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const fine=matchMedia('(hover: hover) and (pointer: fine)');
 const surfaceSelector='.rt-raised,.rt-hero,#sec-idx-card';
 const buttonSelector='button:not(.rt-stock-row):not(.rt-card-title button)';
 let surface=null,button=null,pressed=null,point=null,frame=0;
 let releaseAnimation=null;
 const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
 const closest=(target,selector)=>target instanceof Element?target.closest(selector):null;
 const canTrack=()=>fine.matches&&!reduced.matches&&!document.hidden;
 function resetSurface(){
  if(!surface)return;
  const node=surface.node;
  node.classList.remove('rt-surface-active');
  ['--rt-light-x','--rt-light-y','--rt-tilt-x','--rt-tilt-y','--rt-emblem-x','--rt-emblem-y'].forEach(k=>node.style.removeProperty(k));
  surface=null;
 }
 function resetButton(){
  if(!button)return;
  const node=button.node;
  node.classList.remove('rt-button-active');
  ['--rt-button-x','--rt-button-y','--rt-button-rx','--rt-button-ry','--rt-button-light-x','--rt-button-light-y'].forEach(k=>node.style.removeProperty(k));
  button=null;
 }
 function release(animate=false){
  if(!pressed)return;
  const node=pressed;pressed=null;node.classList.remove('rt-pressing');
  if(animate&&!reduced.matches&&node.isConnected&&!node.disabled){
   if(releaseAnimation)releaseAnimation.cancel();
   releaseAnimation=node.animate([{scale:'.975'},{scale:'1.025',offset:.55},{scale:'1'}],{duration:280,easing:'cubic-bezier(.2,.7,.25,1)'});
  }
 }
 function reset(){
  resetSurface();resetButton();release(false);point=null;
  if(frame)cancelAnimationFrame(frame);frame=0;
  if(releaseAnimation){releaseAnimation.cancel();releaseAnimation=null;}
 }
 function prepare(tree){
  if(!(tree instanceof Element))return;
  if(tree.matches(buttonSelector))tree.classList.add('rt-motion-button');
  tree.querySelectorAll(buttonSelector).forEach(node=>node.classList.add('rt-motion-button'));
 }
 prepare(root);
 function eligibleButton(target){
  const node=closest(target,buttonSelector);
  return node&&!node.disabled&&node.getAttribute('aria-disabled')!=='true'?node:null;
 }
 function choose(target){
  const s=closest(target,surfaceSelector);
  if(s!==surface?.node){
   resetSurface();
   if(s){surface={node:s,rect:s.getBoundingClientRect()};s.classList.add('rt-surface-active');}
  }
  const b=eligibleButton(target);
  if(b!==button?.node){
   resetButton();
   if(b){b.classList.add('rt-motion-button');button={node:b,rect:b.getBoundingClientRect()};b.classList.add('rt-button-active');}
  }
 }
 function paint(){
  frame=0;
  if(!point||!canTrack())return;
  if(surface){
   const {node,rect}=surface;
   if(!node.isConnected||!rect.width||!rect.height){resetSurface();}
   else{
    const x=clamp((point.x-rect.left)/rect.width,0,1),y=clamp((point.y-rect.top)/rect.height,0,1);
    node.style.setProperty('--rt-light-x',(x*100).toFixed(1)+'%');
    node.style.setProperty('--rt-light-y',(y*100).toFixed(1)+'%');
    if(node.matches('.rt-raised')){
     node.style.setProperty('--rt-tilt-x',((.5-y)*3.2).toFixed(2)+'deg');
     node.style.setProperty('--rt-tilt-y',((x-.5)*4).toFixed(2)+'deg');
     node.style.setProperty('--rt-emblem-x',((x-.5)*3).toFixed(2)+'px');
     node.style.setProperty('--rt-emblem-y',((y-.5)*2-1).toFixed(2)+'px');
    }
   }
  }
  if(button){
   const {node,rect}=button;
   if(!node.isConnected||node.disabled||!rect.width||!rect.height){resetButton();}
   else{
    const x=clamp((point.x-rect.left)/rect.width,0,1),y=clamp((point.y-rect.top)/rect.height,0,1);
    node.style.setProperty('--rt-button-x',((x-.5)*4).toFixed(2)+'px');
    node.style.setProperty('--rt-button-y',((y-.5)*3-1).toFixed(2)+'px');
    node.style.setProperty('--rt-button-rx',((.5-y)*6).toFixed(2)+'deg');
    node.style.setProperty('--rt-button-ry',((x-.5)*8).toFixed(2)+'deg');
    node.style.setProperty('--rt-button-light-x',(x*100).toFixed(1)+'%');
    node.style.setProperty('--rt-button-light-y',(y*100).toFixed(1)+'%');
   }
  }
 }
 root.addEventListener('pointermove',e=>{
  if(e.pointerType==='touch'||!canTrack())return;
  point={x:e.clientX,y:e.clientY};choose(e.target);
  if((surface||button)&&!frame)frame=requestAnimationFrame(paint);
 },{passive:true});
 root.addEventListener('pointerout',e=>{
  if(!e.relatedTarget){resetSurface();resetButton();return;}
  if(surface&&closest(e.relatedTarget,surfaceSelector)!==surface.node)resetSurface();
  if(button&&eligibleButton(e.relatedTarget)!==button.node)resetButton();
 },{passive:true});
 root.addEventListener('pointerdown',e=>{
  if(e.button!==0||reduced.matches)return;
  const node=eligibleButton(e.target);if(!node)return;
  release(false);pressed=node;node.classList.add('rt-motion-button','rt-pressing');
 },{passive:true});
 window.addEventListener('pointerup',()=>release(true),{passive:true});
 window.addEventListener('pointercancel',reset,{passive:true});
 root.addEventListener('keydown',e=>{
  if(!['Enter',' '].includes(e.key)||e.repeat||reduced.matches)return;
  const node=eligibleButton(e.target);if(!node)return;
  release(false);pressed=node;node.classList.add('rt-pressing');
 });
 root.addEventListener('keyup',e=>{if(['Enter',' '].includes(e.key))release(true);});
 window.addEventListener('blur',reset);
 window.addEventListener('scroll',reset,{passive:true,capture:true});
 window.addEventListener('resize',reset,{passive:true});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});
 reduced.addEventListener('change',reset);fine.addEventListener('change',reset);
 // Existing views replace their markup after a filter, tab change, or price refresh.
 new MutationObserver(records=>{
  if(surface&&!surface.node.isConnected)resetSurface();
  if(button&&!button.node.isConnected)resetButton();
  if(pressed&&!pressed.isConnected)release(false);
  records.forEach(record=>record.addedNodes.forEach(prepare));
 }).observe(root,{childList:true,subtree:true});
})();

