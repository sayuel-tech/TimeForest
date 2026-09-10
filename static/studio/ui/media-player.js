import {esc} from './primitives.js';

/** A visible play command supplements native controls; state belongs to the media. */
export function mediaPlayer(url, label, note = '', {id='',className=''}={}) {
  if (!url) return `<div class="media-unavailable" role="status">${esc(label)}暂不可用，请检查源视频或重新准备片段。</div>`;
  return `<section class="media-player" data-media-player>
    <div class="media-toolbar"><button type="button" data-media-play aria-label="播放${esc(label)}">▶ 播放</button><span data-media-status role="status">正在读取视频信息…</span><button type="button" data-media-retry hidden>重新加载</button><a href="${esc(url)}" target="_blank" rel="noreferrer" class="quiet">独立打开</a><details class="media-position"><summary>精确定位</summary><input class="media-seek" type="range" min="0" max="1" step=".05" value="0" disabled data-media-seek aria-label="${esc(label)}播放位置"></details></div>
    <video ${id?`id="${esc(id)}"`:''} ${className?`class="${esc(className)}"`:''} controls preload="metadata" playsinline src="${esc(url)}" aria-label="${esc(label)}"></video>
    ${note ? `<p class="media-note">${esc(note)}</p>` : ''}
  </section>`;
}

export function bindMediaPlayers(root) {
  const listeners=[];
  const positions=new Map(),restored=new WeakSet();
  const listen=(type,fn)=>{root.addEventListener(type,fn,true);listeners.push([type,fn]);};
  const update=(video,message)=>{
    const box=video.closest('[data-media-player]');if(!box)return;
    const play=box.querySelector('[data-media-play]');
    play.textContent=video.paused?'▶ 播放':'Ⅱ 暂停';
    play.setAttribute('aria-label',(video.paused?'播放':'暂停')+video.getAttribute('aria-label'));
    box.querySelector('[data-media-status]').textContent=message;
    box.querySelector('[data-media-retry]').hidden=!video.error;
    box.querySelector('.media-toolbar a').href=video.currentSrc||video.src;
  };
  listen('click',async e=>{
    const button=e.target.closest('[data-media-play],[data-media-retry]');if(!button)return;
    const video=button.closest('[data-media-player]').querySelector('video');
    try {
      if(button.hasAttribute('data-media-retry'))video.load();
      if(video.paused){update(video,'正在开始播放…');await video.play();}
      else video.pause();
    } catch(error) {
      if(!video.isConnected || error.name==='AbortError')return;
      update(video,'无法播放：'+(error.name==='NotSupportedError'?'当前浏览器无法解码此视频，请独立打开检查。':error.message));
      video.closest('[data-media-player]').querySelector('[data-media-retry]').hidden=false;
    }
  });
  listen('input',e=>{
    if(!e.target.matches('[data-media-seek]'))return;
    const video=e.target.closest('[data-media-player]').querySelector('video');
    if(Number.isFinite(video.duration))video.currentTime=Math.min(Number(e.target.value),video.duration);
  });
  const syncSeek=video=>{
    const slider=video.closest('[data-media-player]')?.querySelector('[data-media-seek]');if(!slider)return;
    slider.disabled=!Number.isFinite(video.duration);slider.max=video.duration||1;slider.value=video.currentTime;
    slider.setAttribute('aria-valuetext',`${video.currentTime.toFixed(2)} / ${(video.duration||0).toFixed(2)}秒`);
  };
  listen('timeupdate',e=>{if(e.target instanceof HTMLVideoElement){syncSeek(e.target);positions.set(e.target.getAttribute('src'),e.target.currentTime);}});
  listen('durationchange',e=>{if(e.target instanceof HTMLVideoElement)syncSeek(e.target);});
  listen('seeked',e=>{if(e.target instanceof HTMLVideoElement)update(e.target,e.target.paused?'已暂停':'正在播放');});
  for(const [event,message] of [['playing','正在播放'],['pause','已暂停'],['ended','播放结束'],['waiting','正在缓冲…'],['seeking','正在定位…']])
    listen(event,e=>{if(e.target instanceof HTMLVideoElement)update(e.target,message);});
  listen('loadedmetadata',e=>{
    const video=e.target;if(!(video instanceof HTMLVideoElement))return;
    const previous=positions.get(video.getAttribute('src'));
    if(!restored.has(video)&&previous&&Number.isFinite(video.duration))video.currentTime=Math.min(previous,video.duration);
    restored.add(video);syncSeek(video);
    update(video,Number.isFinite(video.duration)?`${video.duration.toFixed(2)} 秒 · 就绪`:'视频已就绪');
  });
  listen('error',e=>{
    if(!(e.target instanceof HTMLVideoElement))return;
    const messages={1:'播放已中止',2:'视频读取失败，请重新加载',3:'视频解码失败',4:'视频格式不支持或文件不可用'};
    update(e.target,messages[e.target.error?.code]||'视频暂时无法播放');
  });
  const dispose=()=>listeners.forEach(([type,fn])=>root.removeEventListener(type,fn,true));
  dispose.refresh=()=>root.querySelectorAll('[data-media-player] video').forEach(video=>{
    syncSeek(video);
    if(video.error)update(video,'视频无法播放，请重新加载');
    else if(video.readyState>=1)update(video,video.paused?`${video.duration.toFixed(2)} 秒 · 已暂停`:'正在播放');
  });
  return dispose;
}
