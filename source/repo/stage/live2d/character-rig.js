/* One writer per facial parameter. A semantic beat rises to a visible peak,
 * softens to a related mild expression, then returns to attentive rest. */
'use strict';
const WhaleCharacterRig = (() => {
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)), smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
  const soft = {
    neutral:{mouth:.04,eye:1},
    warm:{mouth:.75,eye:.8,browY:-.12,browAngle:-.22,browForm:-.12,tilt:-2},
    concerned:{mouth:-.85,eye:.78,browY:.08,browAngle:.5,browForm:-.9,tilt:2.5},
    thoughtful:{mouth:-.08,eye:.85,browY:.1,browAngle:.12,browForm:-.25,tilt:4},
    surprised:{mouth:-.18,eye:1,browY:.45,browAngle:.08,browForm:.3,tilt:-1},
    shy:{mouth:.65,eye:.87,browY:-.12,browAngle:.1,browForm:-.32,tilt:5,blush:.5},
    playful:{mouth:.85,eye:.8,browY:-.06,browAngle:-.28,browForm:.08,tilt:-5,blush:.15},
    firm:{mouth:-.65,eye:.85,browY:-.24,browAngle:-.42,browForm:-.25},
  };
  const strong = {
    neutral:soft.neutral,
    warm:{mouth:1,eye:.38,browY:.15,browAngle:-.35,browForm:.4,tilt:-4,blush:.35},
    excited:{mouth:1,eye:.03,browY:.4,browAngle:-.5,browForm:.7,tilt:-5,blush:.65},
    concerned:{mouth:-1.6,eye:.65,browY:.3,browAngle:1,browForm:-1,tilt:4},
    sad:{mouth:-1.8,eye:.52,browY:.38,browAngle:1,browForm:-1,tilt:5,tears:.65},
    thoughtful:{mouth:-.35,eye:.72,browY:.2,browAngle:.25,browForm:-.45,tilt:6},
    surprised:{mouth:-.65,eye:1,browY:1,browAngle:.3,browForm:.8,tilt:-3,exclamation:1},
    shy:{mouth:.8,eye:.55,browY:-.25,browAngle:.4,browForm:-.6,tilt:8,blush:1},
    playful:{mouth:1,eye:.8,eyeR:.25,browY:.15,browAngle:-.5,browForm:.4,tilt:-7,blush:.4},
    firm:{mouth:-1.2,eye:.62,browY:-.5,browAngle:-.8,browForm:-.65},
    angry:{mouth:-1.6,eye:.48,browY:-.7,browAngle:-1,browForm:-.8,anger:1,tilt:-2},
  };
  const residual={excited:'warm',sad:'concerned',angry:'firm'};
  const names={listening:'认真听你说',thinking:'想一想',neutral:'平静讲解',warm:'开心回应',excited:'好开心！',concerned:'关心你',sad:'有些委屈',thoughtful:'认真思考',surprised:'真的呀！',shy:'害羞了',playful:'开个小玩笑',firm:'认真表达',angry:'认真生气',still:'保持表情'};
  function profileFace(p,strength){
    const base=soft.neutral,a=clamp(Number.isFinite(strength)?strength:.55,0,1),blend=k=>(base[k]||0)+((p[k]||0)-(base[k]||0))*a;
    return {ParamMouthForm:blend('mouth'),ParamEyeLOpen:blend('eye'),ParamEyeROpen:1+((p.eyeR??p.eye??1)-1)*a,
      ParamBrowLY:blend('browY'),ParamBrowRY:blend('browY'),ParamBrowLAngle:blend('browAngle'),ParamBrowRAngle:blend('browAngle'),
      ParamBrowLForm:blend('browForm'),ParamBrowRForm:blend('browForm'),Paramhh2:blend('blush'),
      ParamCheek15:blend('tears'),ParamCheek75:blend('exclamation'),ParamCheek80:blend('anger'),tilt:blend('tilt')};
  }
  function face(expression,strength){return profileFace(strong[expression]||soft.neutral,strength);}
  function beginBeat(previous,cue){
    // TTS may split one meaning into multiple packets. Only a semantic change
    // gets an onset; a new phrase with the same attitude gets a gentler accent.
    if(previous&&previous.segment===cue.segment&&previous.expression===cue.expression)return previous;
    return {segment:cue.segment,expression:cue.expression,intensity:cue.intensity,start:cue.start,
      accent:previous?.expression===cue.expression?.55:1};
  }
  function sample(expression,strength,age=10,silence=0,accent=1){
    const s=clamp(Number.isFinite(strength)?strength:.55,0,1),t=Math.max(0,age);
    // A small configured amplitude remains small. Only expressive beats use
    // comic accents; ordinary conversation doesn't flash symbols repeatedly.
    const peak=(t<.26?smooth(t/.26):t<1.05?1:1-smooth((t-1.05)/1.8))*clamp(accent,0,1);
    const tail=1-smooth(Math.max(0,silence-.15)/3.4);
    const mild=profileFace(soft[residual[expression]||expression]||soft.neutral,s*.5);
    const high=face(expression,s),base=face('neutral',1),value={};
    for(const key of Object.keys(base))value[key]=base[key]+(mild[key]+(high[key]-mild[key])*peak-base[key])*tail;
    const stage=silence>.15?(tail>0?'recovery':'rest'):t<.26?'rising':t<1.05?'peak':t<2.85?'softening':'residual';
    return {face:value,stage,peak:peak*tail,tail};
  }
  function pose(gesture,progress,strength=.65){
    if(progress<=0||progress>=1)return {x:0,y:0,z:0};
    const envelope=Math.sin(Math.PI*progress),a=clamp(strength,0,1);
    if(gesture==='nod')return {x:0,y:6*a*Math.sin(progress*Math.PI*2)*envelope,z:0};
    if(gesture==='shake')return {x:8*a*Math.sin(progress*Math.PI*3)*envelope,y:0,z:0};
    if(gesture==='tilt')return {x:0,y:0,z:5*a*envelope};
    return {x:0,y:0,z:0};
  }
  return {face,sample,pose,names,beginBeat};
})();
if(typeof module!=='undefined')module.exports=WhaleCharacterRig;
