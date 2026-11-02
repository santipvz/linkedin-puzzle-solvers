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

function pageGame() {
  const board = [Array.from('WOFLOO'), Array.from('TRKIMR'), ['O',null,null,'R',null,null],
    ['O',null,null,'R',null,'O'], Array.from('FROORR'), Array.from('OANAGE')];
  const cells = board.flat().map((letter, index) => ({textContent:letter || '',
    getAttribute:name=>name==='data-cell-idx'?String(index):name==='data-cell-is-hole'&&!letter?'true':null}));
  const lengths=[3,5,6,7,8];
  const rows=lengths.map(length=>({querySelectorAll:()=>Array(length).fill({})}));
  const root={querySelectorAll:()=>cells,
    getBoundingClientRect:()=>({left:20,top:40,width:300,height:300,right:320,bottom:340})};
  const context=vm.createContext({document:{querySelector:()=>root,querySelectorAll:()=>rows},
    window:{self:{},top:{},innerWidth:400,innerHeight:400,devicePixelRatio:1},
    chrome:{runtime:{onMessage:{addListener(){}}}}});
  for(const file of ['puzzle_registry.js','content.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'..',file),'utf8'),context);
  return {context,cells,rows,board};
}

test('Wend reads all letters and holes by index and counts answer slots without OCR',()=>{
  const {context,cells,board}=pageGame();cells.reverse();
  const read=JSON.parse(JSON.stringify(context.readWendPageBoard()));
  assert.deepEqual(read.board,board);assert.deepEqual(read.lengths,[3,5,6,7,8]);
  assert.equal(read.selection.width,300);
});

test('Wend falls back to the image for incomplete, duplicate or unreadable page cells',()=>{
  for(const corrupt of [
    game=>game.cells.pop(),
    game=>game.cells[1].getAttribute=name=>name==='data-cell-idx'?'0':null,
    game=>game.cells[0].textContent='?',
    game=>game.cells[0].textContent='',
    game=>game.rows.pop(),
  ]) {
    const game=pageGame();corrupt(game);assert.equal(game.context.readWendPageBoard(),null);
  }
});

test('Wend only sends page data when its live geometry matches the captured board',async()=>{
  const context=vm.createContext({chrome:{runtime:{onMessage:{addListener(){}}}}});
  for(const file of ['puzzle_registry.js','api_config.js','background.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'..',file),'utf8'),context);
  const selection={x:20,y:40,width:300,height:300,devicePixelRatio:1};
  context.tabsGet=async()=>({windowId:1});context.captureVisibleTab=async()=>'';
  context.cropCapturedImage=async()=>({});context.getGameFrameContext=async()=>({gameFrameId:0});
  context.safeSendTabMessage=async()=>({ok:true,parsedBoard:{board:[],lengths:[],selection}});
  let options;
  context.callSolverApi=async(_base,_puzzle,_image,value)=>{options=value;return {};};
  await context.solveBoardCore({tabId:1,puzzleType:'wend',apiBaseUrl:'http://localhost',selection});
  assert.ok(options.parsedBoard);
  await context.solveBoardCore({tabId:1,puzzleType:'wend',apiBaseUrl:'http://localhost',selection:{...selection,x:400}});
  assert.equal(options.parsedBoard,null);
});

test('the API upload includes page data only for Wend and preserves the image capture',async()=>{
  let request;
  const context=vm.createContext({Blob,FormData,chrome:{runtime:{onMessage:{addListener(){}}}},
    fetch:async(url,options)=>{request={url,...options};return {ok:true,text:async()=>'{"solved":true}'};}});
  for(const file of ['puzzle_registry.js','api_config.js','background.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'..',file),'utf8'),context);
  const board={board:[['A']],lengths:[1]}, image=new Blob(['image'],{type:'image/png'});
  await context.callSolverApi('http://127.0.0.1:18000','wend',image,{parsedBoard:board,captureBoardStart:true});
  assert.equal(request.url,'http://127.0.0.1:18000/solve/wend');
  assert.deepEqual(JSON.parse(request.body.get('parsed_board')),board);
  assert.equal(await request.body.get('image').text(),'image');
  assert.equal(request.headers['X-Board-Capture'],'start');
  await context.callSolverApi('http://127.0.0.1:18000','zip',image,{parsedBoard:board});
  assert.equal(request.body.has('parsed_board'),false);
});
