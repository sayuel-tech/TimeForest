import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceParametersMarkup} from '../static/studio/modes/video-assembly/source-parameters.js';

test('source settings are optional, escaped, read-only and initially collapsed',()=>{
  assert.equal(sourceParametersMarkup(undefined),'');assert.equal(sourceParametersMarkup([]),'');
  const html=sourceParametersMarkup([{title:'原片段',fields:[{group:'core',label:'底模',value:'<script>bad</script>'},{group:'sampling',label:'种子',value:'0'},{group:'memory',label:'低显存',value:false}]}]);
  assert.match(html,/&lt;script&gt;/);assert.match(html,/<dd>0<\/dd>/);assert.match(html,/<dd>关闭<\/dd>/);
  assert.doesNotMatch(html,/<script>|<input|<select|<textarea|<details[^>]* open/);
});
