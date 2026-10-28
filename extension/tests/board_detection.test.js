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
