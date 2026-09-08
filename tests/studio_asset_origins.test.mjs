import test from 'node:test';
import assert from 'node:assert/strict';
import {assetOriginMarkup,assetVersionLink,projectOriginLink,lineageMarkup} from '../static/studio/ui/asset-origin.js';
import {referenceAssetCard} from '../static/studio/ui/reference-assets.js';
import {sourceParametersMarkup} from '../static/studio/ui/source-parameters.js';

test('来源项目按可用、移除、缺失区分；名称与参数不能注入HTML',()=>{
  assert.match(projectOriginLink({id:'p',name:'<script>',state:'available',url:'#/p/p'}),/href="#\/p\/p"/);
  assert.match(projectOriginLink({name:'<script>',state:'missing'}),/&lt;script&gt;/);
  assert.doesNotMatch(projectOriginLink({name:'旧项目',state:'missing'}),/<a /);
  assert.match(projectOriginLink({name:'旧项目',state:'removed'}),/项目回收站/);
  const html=assetOriginMarkup({chain:[{name:'资产',type:'local',project:null}],prompt:'<img onerror=x>',parameters:[]});
  assert.match(html,/未记录来源项目/);assert.match(html,/&lt;img onerror=x&gt;/);
});
test('派生链默认折叠、关系分组、精确跳转及异常不冒充可用',()=>{
  const html=lineageMarkup({version:1,truncated:true,rows:[
    {id:1,parent:null,relation:'continuation',kind:'assembly',run:'<script>',project:{name:'项目',state:'available',url:'#/p/p?origin_run=old'},state:'removed'},
    {id:2,parent:1,relation:'image_B',kind:'asset',asset:'a',version:'v',media:'m',state:'available'},
    {id:3,parent:null,relation:'derived',kind:'asset',asset:'missing',version:'v',state:'missing',notice:'<img>'}
  ]});
  assert.match(html,/<details class="asset-lineage">/);assert.doesNotMatch(html,/<details[^>]* open/);
  assert.match(html,/视频承接自/);assert.match(html,/参考图片 B/);assert.match(html,/来自第 1 项/);
  assert.match(html,/origin_run=old/);assert.match(html,/version=v&amp;media=m/);
  assert.doesNotMatch(html,/href="[^" ]*missing/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img&gt;/);
  assert.match(html,/展开上限/);assert.match(lineageMarkup(undefined),/当前后台/);
});
test('固定素材链接带确切版本与媒体，公共参考卡使用相同入口',()=>{
  const ref={asset:'asset',version:'old',media:'second'};
  assert.match(assetVersionLink(ref),/version=old&amp;media=second/);
  assert.match(referenceAssetCard({name:'角色',kind:'image',url:'/img',library_reference:ref}),/查看库内素材与来源/);
  assert.equal(assetVersionLink({asset:'x'}),'');
});
test('制作记录与原有接续使用同一呈现，零值保留且不暴露应用动作',()=>{
  const html=sourceParametersMarkup([{title:'制作参数',fields:[{label:'种子',group:'sampling',value:0}]}],{title:'查看制作时参数'});
  assert.match(html,/>0</);assert.match(html,/查看制作时参数/);assert.doesNotMatch(html,/data-settings-action/);
  const data=assetOriginMarkup({chain:[{name:'派生',type:'derived'},{asset:'a',version:'v',media:'m',name:'父资产'}],parts:[{index:1,run:'p11',start:0,end:5}],parameters:[]});
  assert.match(data,/上游资产/);assert.match(data,/合成顺序/);assert.match(data,/p11/);
});
