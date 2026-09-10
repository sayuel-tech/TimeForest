/** Times are still stored and submitted as integer milliseconds. */
export function formatTimecode(value) {
  const ms=Number(value);
  if(!Number.isSafeInteger(ms)||ms<0)return '';
  return `${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms%60000/1000)).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
}
export function parseTimecode(value) {
  const text=String(value).trim();
  if(!text)return null;
  let total;
  if(/^\d+(?:\.\d{1,3})?$/.test(text))total=Math.round(Number(text)*1000);
  else {
    const match=text.match(/^(\d+):([0-5]\d)(?:\.(\d{1,3}))?$/);
    if(!match)return null;
    total=Number(match[1])*60000+Number(match[2])*1000+Number((match[3]||'').padEnd(3,'0'));
  }
  return Number.isSafeInteger(total)&&total>=0?total:null;
}

/** Keep the original input and its business handler: only change its presentation. */
export function bindTimecodeInputs(root,{duration=null,onDraftInput=()=>{},drafts=new Map(),scope=''}={}) {
  root.querySelectorAll('input[data-range],input[data-upstream-range]').forEach(original=>{
    if(original.dataset.timecodeEnhanced)return;
    original.dataset.timecodeEnhanced='true';
    const label=original.closest('label');
    const span=label?.querySelector(':scope > span');
    if(span)span.textContent=span.textContent.replace(/（毫秒）|\(毫秒\)/g,'');
    const wrap=document.createElement('div');wrap.className='timecode-control';
    original.before(wrap);wrap.append(original);
    original.classList.add('timecode-ms');original.tabIndex=-1;original.setAttribute('aria-hidden','true');
    const human=document.createElement('input');human.type='text';human.inputMode='decimal';human.autocomplete='off';human.spellcheck=false;
    human.className='timecode-display';human.dataset.timecodeKey=(original.hasAttribute('data-range')?'edit:':'upstream:')+(original.dataset.range||original.dataset.upstreamRange);human.value=formatTimecode(Number(original.value));
    const draftKey=scope+':'+human.dataset.timecodeKey;
    const min=original.min!==''?Number(original.min):0;
    const max=Number.isFinite(duration)?duration:null;
    if(drafts.has(draftKey))human.value=drafts.get(draftKey).text;
    human.setAttribute('aria-label',(span?.textContent||'采用位置')+'，分:秒.毫秒');
    human.id='timecode-'+draftKey.replaceAll(':','-');if(label)label.htmlFor=human.id;
    human.placeholder='00:07.250';human.disabled=original.disabled;wrap.append(human);
    const hint=document.createElement('small');hint.className='timecode-validation';hint.setAttribute('role','status');wrap.append(hint);
    function validate(){
      const value=parseTimecode(human.value);
      const valid=value!==null&&value>=min&&(max===null||value<=max);
      human.setCustomValidity(valid?'':'请输入有效时间，例如 00:07.250。');
      human.setAttribute('aria-invalid',String(!valid));hint.textContent=valid?'':'请输入有效时间；当前输入尚未写入剪辑。';
      return valid?value:null;
    }
    validate();
    human.addEventListener('input',()=>{
      onDraftInput();drafts.set(draftKey,{text:human.value,min,max});
      const value=validate();if(value===null)return;
      original.value=String(value);original.dispatchEvent(new Event('input',{bubbles:true}));
    });
    human.addEventListener('blur',()=>{if(human.checkValidity()){human.value=formatTimecode(Number(original.value));if(drafts.has(draftKey))drafts.set(draftKey,{text:human.value,min,max});}});
    original.addEventListener('input',()=>{if(document.activeElement!==human)human.value=formatTimecode(Number(original.value));});
  });
}

/** Used by the original save gate, including save-before-leave (not only clicks). */
export function assertTimecodeInputs(root,drafts=new Map()){
  const invalid=[...drafts.values()].some(({text,min,max})=>{const n=parseTimecode(text);return n===null||n<min||(max!==null&&n>max);});
  for(const human of root.querySelectorAll('.timecode-display')){
    if(parseTimecode(human.value)===null||!human.checkValidity()){
      human.focus();human.reportValidity();
      throw new Error('采用时间尚未填写正确，当前输入已保留。请使用 00:07.250 这样的格式。');
    }
  }
  if(invalid)throw new Error('有尚未填写正确的时间码，请返回对应片段修改；输入已保留。');
  for(const selector of ['data-range','data-upstream-range']){
    const start=root.querySelector(`[${selector}="in_ms"]`),end=root.querySelector(`[${selector}="out_ms"]`);
    if(start&&end&&Number(end.value)<=Number(start.value))throw new Error('出点必须晚于入点。当前区间已保留，但尚未保存。');
  }
}
