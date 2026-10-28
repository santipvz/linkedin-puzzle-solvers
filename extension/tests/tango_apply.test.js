const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function game(options = {}) {
  const grid = Array.from({length:6}, (_,r) => Array.from({length:6},(_,c)=>(r+c)%2));
  const fixed = [0,7,14,21,28,35];
  const values = grid.flat().map((v,i)=>fixed.includes(i)?v:-1);
  values[1] = grid.flat()[1]; // A correct existing answer must not be cycled.
  values[3] = 1 - grid.flat()[3];
  const writes = [];
  let pending;
  class Cell {
    constructor(index) { this.index = index; }
    getBoundingClientRect() { const left=20+this.index%6*50,top=20+Math.floor(this.index/6)*50;return {left,top,width:50,height:50,right:left+50,bottom:top+50}; }
    getAttribute(name) { return name === 'aria-disabled' ? String(fixed.includes(this.index)) : null; }
    querySelector(selector) { const type=values[this.index]===1?'zero':values[this.index]===0?'one':'empty';return selector===`[data-testid="cell-${type}"]`?{}:null; }
    dispatchEvent(event) {
      if(event.type==='click') {
        writes.push(this.index);
        if(options.ignoreClicks) return true;
        const update=()=>{const i=options.wrongCell?(this.index+1)%36:this.index;values[i]=values[i]===-1?1:values[i]===1?0:-1;};
        if(options.delayed) pending=update; else update();
      }
      return true;
    }
  }
  const cells=values.map((_,i)=>new Cell(i));
  const context=vm.createContext({
    window:{self:{},top:{},innerWidth:400,innerHeight:400,location:{pathname:'/games/tango/'}},
    document:{getElementById:id=>cells[Number(id.replace('tango-cell-',''))]||null,
      elementFromPoint:(x,y)=>cells[Math.floor((y-20)/50)*6+Math.floor((x-20)/50)],body:{innerText:''}},
    chrome:{runtime:{onMessage:{addListener(){}}}},
    HTMLIFrameElement:class{},MouseEvent:class{constructor(type,data){this.type=type;Object.assign(this,data);}},
  });
  for(const file of ['puzzle_registry.js','content.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'..',file),'utf8'),context);
  context.sleep=async()=>{if(pending){const update=pending;pending=null;update();}};
  const result={solved:true,board_size:6,solution_grid:grid,fixed_pieces:fixed.map(i=>({row:Math.floor(i/6),col:i%6,piece_type:grid.flat()[i]}))};
  return {context,values,writes,result,apply:()=>context.applyTangoSolution(result,{x:0,y:0,width:220,height:220},{interClickDelayMs:0,interMoveDelayMs:0})};
}

test('Tango uses live cells even when supplied image coordinates are stale, and corrects existing pieces',async()=>{
  const g=game({delayed:true});const r=await g.apply();assert.equal(r.ok,true);assert.deepEqual(g.values,g.result.solution_grid.flat());assert.ok(!g.writes.includes(1));assert.equal(g.writes.filter(i=>i===3).length,2);
});
test('Tango rejects a solution that contradicts the original fixed pieces before any clicks',async()=>{
  const g=game();g.result.solution_grid[0][0]=1-g.result.solution_grid[0][0];assert.equal((await g.apply()).ok,false);assert.deepEqual(g.writes,[]);
});
test('Tango rejects a cropped parse with a different set of fixed clues',async()=>{
  const g=game();g.result.fixed_pieces.pop();assert.equal((await g.apply()).ok,false);assert.deepEqual(g.writes,[]);
});
test('Tango reports ignored clicks as failure without replaying',async()=>{
  const g=game({ignoreClicks:true});assert.equal((await g.apply()).ok,false);assert.equal(g.writes.length,1);
});
test('Tango stops if an input changes another cell',async()=>{
  const g=game({wrongCell:true});assert.equal((await g.apply()).ok,false);assert.equal(g.writes.length,1);
});
