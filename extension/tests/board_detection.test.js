const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

function scripts(context, files) {
  for (const file of files) vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
}

test("detects Queens from its section landmark with opaque CSS classes and role note", () => {
  const rect = { left: 528, top: 97, width: 416, height: 416, right: 944, bottom: 513 };
  const board = { tagName: "SECTION", className: "ajrmrz ajrmry", role: "note", getBoundingClientRect: () => rect };
  const context = vm.createContext({
    document: { querySelector: (selector) => selector === "#queens-game-board" ? board : null,
      querySelectorAll: () => [] },
    window: { self: {}, top: {}, innerWidth: 1487, innerHeight: 692, devicePixelRatio: 1.25 },
    chrome: { runtime: { onMessage: { addListener() {} } } },
  });
  scripts(context, ["puzzle_registry.js", "content.js"]);
  assert.deepEqual(JSON.parse(JSON.stringify(context.autoDetectBoardSelection("queens"))),
    { x: 528, y: 97, width: 416, height: 416, devicePixelRatio: 1.25 });
});

test("explicit board detection bypasses a cached viewport selection", async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  scripts(context, ["puzzle_registry.js", "api_config.js", "background.js"]);
  const selection = { x: 528, y: 97, width: 416, height: 416, devicePixelRatio: 1.25 };
  context.getTopBoardSelection = async () => { throw new Error("Must not reuse a cached fallback"); };
  context.safeSendTabMessage = async () => ({ selection });
  context.setTopBoardSelection = async (_, value) => value;
  context.resolveInteractionTarget = (value) => ({ frameId: 0, selection: value });
  const response = await context.detectSelectionForQuickSolve(1, "queens", {}, {}, { forceDetect: true });
  assert.equal(response.topSelection.x, 528);
  assert.equal(response.topSelection.width, 416);
});

test('quick solve measures a new board instead of reusing coordinates from another game or scroll', async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  scripts(context, ['puzzle_registry.js', 'api_config.js', 'background.js']);
  context.getTopBoardSelection = async () => { throw new Error('Cached coordinates must not be read'); };
  const selection = {x:530,y:150,width:416,height:416,devicePixelRatio:1.25};
  context.safeSendTabMessage = async () => ({selection});
  context.setTopBoardSelection = async (_, value) => value;
  context.resolveInteractionTarget = value => ({frameId:0,selection:value});
  for (const puzzle of ['wend','patches','sudoku','tango']) {
    const response = await context.detectSelectionForQuickSolve(1,puzzle,{},{});
    assert.equal(response.topSelection.y,150);
  }
});

test('a reliable Tango board with six givens and three signs is accepted before searching smaller crops', () => {
  const context = vm.createContext({chrome:{runtime:{onMessage:{addListener(){}}}}});
  scripts(context,['puzzle_registry.js','api_config.js','background.js']);
  assert.equal(context.isConfidentTangoAttempt({solved:true,moves:[{}],details:{fixed_count:6,constraint_count:3,parse_reliable:true}},4112),true);
  assert.equal(context.isConfidentTangoAttempt({solved:true,moves:[{}],details:{fixed_count:12,constraint_count:9,parse_reliable:false}},9999),false);
});

test('preparing a partly scrolled Wend board brings it into view and waits for stable bounds', async () => {
  let top=-100,scrolled=false;
  const board={getBoundingClientRect:()=>({left:20,top,width:300,height:300,right:320,bottom:top+300}),
    scrollIntoView(){scrolled=true;top=40;}};
  const context=vm.createContext({document:{querySelector:selector=>selector==='[data-testid="wend-game-board"]'?board:null},
    window:{self:{},top:{},innerWidth:400,innerHeight:400,devicePixelRatio:1},
    chrome:{runtime:{onMessage:{addListener(){}}}}});
  scripts(context,['puzzle_registry.js','content.js']);context.sleep=async()=>{};
  const selection=await context.prepareBoardCapture('wend');
  assert.equal(scrolled,true);assert.equal(selection.y,40);assert.equal(selection.height,300);
});

function sudokuCapture({top=40, left=40, frame=true}={}) {
  let scrolled=false;
  const rect=(x,y,size)=>({left:x,top:y,width:size,height:size,right:x+size,bottom:y+size});
  const outer={getBoundingClientRect:()=>rect(left-4,top-4,308),
    scrollIntoView(){scrolled=true;top=40;}};
  const grid={getBoundingClientRect:()=>rect(left,top,300),closest:selector=>frame&&selector==='.sudoku-board'?outer:null,
    scrollIntoView(){scrolled=true;top=40;}};
  const context=vm.createContext({document:{querySelector:selector=>selector==='.sudoku-grid'?grid:null},
    window:{self:{},top:{},innerWidth:400,innerHeight:400,devicePixelRatio:1.25},
    chrome:{runtime:{onMessage:{addListener(){}}}}});
  scripts(context,['puzzle_registry.js','content.js']);context.sleep=async()=>{};
  return {context,get scrolled(){return scrolled;}};
}

test('Sudoku captures its parent border and a rounding margin while native apply bounds stay on cells',async()=>{
  const {context}=sudokuCapture();
  const capture=JSON.parse(JSON.stringify(await context.prepareBoardCapture('sudoku')));
  assert.deepEqual(capture,{x:28,y:28,width:324,height:324,devicePixelRatio:1.25});
  const apply=JSON.parse(JSON.stringify(context.nativeBoardSelection('sudoku')));
  assert.deepEqual(apply,{x:40,y:40,width:300,height:300,devicePixelRatio:1.25});
});

test('Sudoku scrolls when the frame is clipped even if all inner cells are visible',async()=>{
  const game=sudokuCapture({top:2});
  const selection=await game.context.prepareBoardCapture('sudoku');
  assert.equal(game.scrolled,true);assert.equal(selection.y,28);
});

test('Sudoku clips only the capture margin at a viewport edge',async()=>{
  const {context}=sudokuCapture({top:4,left:4});
  const capture=await context.prepareBoardCapture('sudoku');
  assert.equal(capture.x,0);assert.equal(capture.y,0);
  assert.equal(capture.width,316);assert.equal(capture.height,316);
});

test('Sudoku capture still works when the page does not expose the outer wrapper',async()=>{
  const {context}=sudokuCapture({frame:false});
  const capture=await context.prepareBoardCapture('sudoku');
  assert.equal(capture.x,32);assert.equal(capture.width,316);
});

test('Sudoku capture reacquires the live frame when the page replaces the grid',async()=>{
  const {context}=sudokuCapture();
  const rect={left:56,top:56,width:308,height:308,right:364,bottom:364};
  const replacement={closest:()=>({getBoundingClientRect:()=>rect})};
  let waits=0;
  context.sleep=async()=>{
    if(++waits===2)context.document.querySelector=()=>replacement;
  };
  const capture=await context.prepareBoardCapture('sudoku');
  assert.equal(capture.x,48);assert.equal(capture.y,48);
  assert.equal(waits,3);
});
