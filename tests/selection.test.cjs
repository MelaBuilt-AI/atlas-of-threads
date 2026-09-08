const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../viz/dist/space.js'), 'utf8');
const cycle = source.slice(source.indexOf('  function cycleChoice('), source.indexOf('  function previewChoice('));

test('both directions include the arrival object exactly once and recenter without entering a graph', () => {
  const ctx={navigating:false,walk:{reflecting:false}, focusIndex:-1,
    choices:[0,1,2].map(mesh=>({mesh,choice:{audioRole:'story'}})),
    clockwiseChoices:()=>[{index:2},{index:0},{index:1}],
    focusCameraOn:mesh=>{ctx.camera=mesh;}, resetCameraFocus:()=>{ctx.camera='center';},
    showFocus:()=>{},sound:{cycle:()=>{}}};
  vm.createContext(ctx); vm.runInContext(cycle,ctx);
  for(const [direction, expected] of [[1,[2,0,1,-1]],[-1,[1,0,2,-1]]]) {
    for(const next of expected) { ctx.cycleChoice(direction); assert.equal(ctx.focusIndex,next); }
    assert.equal(ctx.camera,'center');
  }
  ctx.walk.reflecting=true; ctx.cycleChoice(1); assert.equal(ctx.focusIndex,-1);
  ctx.walk.reflecting=false; ctx.navigating=true; ctx.cycleChoice(1); assert.equal(ctx.focusIndex,-1);
  ctx.navigating=false;ctx.choices=[];ctx.cycleChoice(1);assert.equal(ctx.focusIndex,-1);
});
