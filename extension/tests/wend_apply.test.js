const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function game({accept = true, partial = false} = {}) {
  const locked = new Set(partial ? [0] : []);
  const cells = Array.from({length:9},(_,i)=>({getAttribute:()=>locked.has(i)?'true':null,
    getBoundingClientRect:()=>({left:20+i%3*60,top:40+Math.floor(i/3)*60,width:60,height:60})}));
  const board={querySelector:selector=>cells[Number(selector.match(/"(\d+)"/)[1])]};
  const context=vm.createContext({document:{querySelector:()=>board},window:{self:{},top:{},innerWidth:400,innerHeight:400,location:{pathname:'/games/wend/'}},
    chrome:{runtime:{onMessage:{addListener(){}}}}});
  for(const file of ['puzzle_registry.js','wend_paths.js','content.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'..',file),'utf8'),context);
  let drags=0,points;
  context.sleep=async()=>{};
  context.dragViewportPath=async value=>{drags++;points=JSON.parse(JSON.stringify(value));if(accept)[0,1,2].forEach(i=>locked.add(i));return true;};
  const result={solved:true,board_size:3,words:[{word:'CAT',path:[{row:0,col:0},{row:0,col:1},{row:0,col:2}]}]};
  return {apply:()=>context.applyWendSolution(result,{x:200,y:200,width:90,height:90},{}),get drags(){return drags;},get points(){return points;}};
}

test('Wend follows current cells and verifies that the game locks the accepted word',async()=>{
  const g=game();assert.equal((await g.apply()).ok,true);assert.deepEqual(g.points,[{x:50,y:70},{x:110,y:70},{x:170,y:70}]);
  assert.equal((await g.apply()).appliedCount,0);assert.equal(g.drags,1);
});
test('Wend does not report a dispatched but rejected word path as applied',async()=>{
  const g=game({accept:false});assert.equal((await g.apply()).ok,false);assert.equal(g.drags,1);
});
test('Wend stops before overwriting part of an already accepted word',async()=>{
  const g=game({partial:true});assert.equal((await g.apply()).ok,false);assert.equal(g.drags,0);
});
