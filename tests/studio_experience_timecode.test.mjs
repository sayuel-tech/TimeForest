import test from 'node:test';
import assert from 'node:assert/strict';
import {parseTimecode,formatTimecode} from '../static/studio/ui/timecode-input.js';

test('timecode accepts milliseconds without binary-float drift',()=>{
 for(const [input,result] of [['00:07.250',7250],['7.250',7250],['0',0],['01:00',60000],['1:05.2',65200],['999:59.999',59999999]])
  assert.equal(parseTimecode(input),result,input);
});
test('timecode rejects malformed, negative and unsafe values',()=>{
 for(const input of ['', 'abc','-1','00:60.000','00:07.1234','1e6','Infinity','9007199254740993'])assert.equal(parseTimecode(input),null,input);
});
test('timecodes round trip exact integer milliseconds',()=>{
 for(const value of [0,1,99,999,1000,59999,60000,999999,3600000,99999999])assert.equal(parseTimecode(formatTimecode(value)),value);
 assert.equal(formatTimecode(-1),'');assert.equal(formatTimecode(.1),'');assert.equal(formatTimecode(NaN),'');
});
