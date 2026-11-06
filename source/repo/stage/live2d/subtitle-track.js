/* Two-line captions sized to the actual player. Page timing follows each audio
 * chunk proportionally; this is not word-level forced alignment. */
'use strict';
window.SubtitleTrack={create(element){
 const measure=document.createElement('canvas').getContext('2d');
 const segmenter=typeof Intl.Segmenter==='function'?new Intl.Segmenter('zh',{granularity:'grapheme'}):null;
 let dirty=true,lastText=null,pages=[],visible=null;
 const resize=new ResizeObserver(()=>{dirty=true;});resize.observe(element);
 if(document.fonts)document.fonts.ready.then(()=>{dirty=true;});
 function layout(text){
  const style=getComputedStyle(element);
  measure.font=style.font||`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const width=Math.max(1,element.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-2);
  const letters=segmenter?Array.from(segmenter.segment(text),x=>x.segment):Array.from(text);
  const lines=[];let line='',start=0,offset=0;
  for(const letter of letters){
   if(letter==='\n'||(line&&measure.measureText(line+letter).width>width)){
    lines.push({text:line,start,end:offset});line='';start=offset;
   }
   if(letter!=='\n')line+=letter;
   offset+=letter.length;
  }
  if(line)lines.push({text:line,start,end:offset});
  pages=[];
  for(let i=0;i<lines.length;i+=2)pages.push({text:lines.slice(i,i+2).map(x=>x.text).join('\n'),start:lines[i].start});
 }
 return {show(text,progress=0){
  text=String(text||'');
  if(dirty||text!==lastText){layout(text);lastText=text;dirty=false;}
  const cursor=Math.max(0,Math.min(.999999,progress))*text.length;
  let page=pages[0];for(const next of pages){if(next.start>cursor)break;page=next;}
  const value=page?.text||'';
  if(value!==visible){element.textContent=value;visible=value;}
 },reset(){lastText=null;dirty=true;},pages(){return pages.map(p=>p.text);}};
}};
