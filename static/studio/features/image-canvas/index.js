/** Canvas geometry is in normalized source pixels; CSS zoom never changes the mask. */
export class ImageCanvas {
  constructor(host,{image,mask,mode,geometry,settings,onChange,onPad}){
    Object.assign(this,{host,mode,geometry,settings,onChange,onPad});
    this.autoFit=true;
    this.tool='brush';this.brush=40;this.visible=true;this.changed=false;this.undo=[];this.redo=[];
    this.canvas=host.querySelector('canvas');this.ctx=this.canvas.getContext('2d');
    this.mask=document.createElement('canvas');this.mctx=this.mask.getContext('2d',{willReadFrequently:true});
    this.image=new Image();this.image.onload=async()=>{
      if(!this.host.isConnected)return;
      this.mask.width=this.image.naturalWidth;this.mask.height=this.image.naturalHeight;
      if(mask){
        const saved=new Image();await new Promise((ok,no)=>{saved.onload=ok;saved.onerror=no;saved.src=mask;}).catch(()=>{});
        if(saved.naturalWidth){this.mctx.drawImage(saved,0,0);const d=this.mctx.getImageData(0,0,this.mask.width,this.mask.height);
          for(let i=0;i<d.data.length;i+=4){d.data[i+3]=d.data[i];d.data[i]=d.data[i+1]=d.data[i+2]=255;}this.mctx.putImageData(d,0,0);}
      }
      this.draw();this.fit();
    };this.image.src=image;
    this.bind();
    this.resizeObserver=new ResizeObserver(()=>{if(this.autoFit&&this.image.naturalWidth)this.fit();});
    this.resizeObserver.observe(host);
  }
  bind(){
    const c=this.canvas;
    c.onpointerdown=e=>{
      if(!this.image.naturalWidth)return;
      c.setPointerCapture(e.pointerId);
      this.drag={x:e.clientX,y:e.clientY,left:this.host.scrollLeft,top:this.host.scrollTop};
      if(this.tool==='pan'||e.button===1){this.drag.pan=true;return;}
      const pt=this.point(e);
      if(this.mode==='region'){
        const max=Math.max(1,Math.min(12,Math.floor(64*1024*1024/(this.mask.width*this.mask.height*4))));
        this.undo.push(this.mctx.getImageData(0,0,this.mask.width,this.mask.height));if(this.undo.length>max)this.undo.shift();this.redo=[];
        this.drag.last=pt;this.stroke(pt,pt);
      }else if(this.mode==='outpaint'){
        const distances={left:pt.x,right:c.width-pt.x,top:pt.y,bottom:c.height-pt.y};
        this.drag.edge=Object.keys(distances).sort((a,b)=>distances[a]-distances[b])[0];
        this.drag.pad={...this.settings};this.drag.start=pt;
      }
    };
    c.onpointermove=e=>{
      if(!this.drag)return;
      if(this.drag.pan){this.host.scrollLeft=this.drag.left-(e.clientX-this.drag.x);this.host.scrollTop=this.drag.top-(e.clientY-this.drag.y);return;}
      const pt=this.point(e);
      if(this.mode==='region'){this.stroke(this.drag.last,pt);this.drag.last=pt;}
    };
    c.onpointerup=e=>{
      if(this.drag?.edge){const pt=this.point(e),edge=this.drag.edge;
        const delta=['left','right'].includes(edge)?pt.x-this.drag.start.x:pt.y-this.drag.start.y;
        this.onPad(edge,Math.max(0,Math.round(this.drag.pad[edge]+delta*(['left','top'].includes(edge)?-1:1))));}
      this.drag=null;
    };
    c.onpointercancel=()=>{this.drag=null;};
  }
  point(e){const r=this.canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*this.canvas.width/r.width,y:(e.clientY-r.top)*this.canvas.height/r.height};}
  stroke(a,b){
    this.lastAction='stroke';
    const ctx=this.mctx;ctx.globalCompositeOperation=this.tool==='erase'?'destination-out':'source-over';ctx.strokeStyle='white';ctx.fillStyle='white';ctx.lineWidth=this.brush;ctx.lineCap='round';ctx.lineJoin='round';
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.beginPath();ctx.arc(b.x,b.y,this.brush/2,0,2*Math.PI);ctx.fill();
    ctx.globalCompositeOperation='source-over';this.changed=true;this.onChange();this.draw();
  }
  draw(){
    if(!this.image.naturalWidth)return;
    const size=this.mode==='outpaint'&&this.geometry?this.geometry.canvas:[this.image.naturalWidth,this.image.naturalHeight];
    const c=this.canvas,ctx=this.ctx;if(c.width!==size[0]||c.height!==size[1]){c.width=size[0];c.height=size[1];}
    ctx.clearRect(0,0,c.width,c.height);
    if(this.mode==='outpaint'&&this.geometry){ctx.fillStyle='#b8c6e0';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(this.image,this.settings.left,this.settings.top,...this.geometry.work);ctx.strokeStyle='#3b639b';ctx.lineWidth=Math.max(2,c.width/300);ctx.strokeRect(1,1,c.width-2,c.height-2);}
    else{ctx.drawImage(this.image,0,0);if(this.mode==='region'&&this.visible){const tint=document.createElement('canvas');tint.width=c.width;tint.height=c.height;const t=tint.getContext('2d');t.drawImage(this.mask,0,0);t.globalCompositeOperation='source-in';t.fillStyle='rgba(45,100,220,.52)';t.fillRect(0,0,c.width,c.height);ctx.drawImage(tint,0,0);}}
    if(this.zoom)this.setZoom(this.zoom,false);
  }
  fit(){this.setZoom(Math.min(1,(this.host.clientWidth-24)/this.canvas.width,(this.host.clientHeight-24)/this.canvas.height),false);this.autoFit=true;}
  setZoom(value,manual=true){if(manual)this.autoFit=false;this.zoom=Math.max(.03,Math.min(4,value));this.canvas.style.width=this.canvas.width*this.zoom+'px';this.canvas.style.height=this.canvas.height*this.zoom+'px';}
  action(action){
    if(action==='undo'&&this.undo.length){this.redo.push(this.mctx.getImageData(0,0,this.mask.width,this.mask.height));this.mctx.putImageData(this.undo.pop(),0,0);}
    else if(action==='redo'&&this.redo.length){this.undo.push(this.mctx.getImageData(0,0,this.mask.width,this.mask.height));this.mctx.putImageData(this.redo.pop(),0,0);}
    else if(action==='clear'){this.undo.push(this.mctx.getImageData(0,0,this.mask.width,this.mask.height));this.mctx.clearRect(0,0,this.mask.width,this.mask.height);this.redo=[];}
    else return;
    this.lastAction=action;this.changed=true;this.onChange();this.draw();
  }
  blob(){const c=document.createElement('canvas');c.width=this.mask.width;c.height=this.mask.height;const x=c.getContext('2d');x.fillStyle='black';x.fillRect(0,0,c.width,c.height);x.drawImage(this.mask,0,0);return new Promise(resolve=>c.toBlob(resolve,'image/png'));}
  dispose(){this.resizeObserver.disconnect();this.image.onload=null;this.drag=null;this.canvas.onpointerdown=this.canvas.onpointermove=this.canvas.onpointerup=null;}
}
