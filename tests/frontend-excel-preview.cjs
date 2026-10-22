/* The Excel preview draws the same form-style tables the file is written from: label cells, merged cells, hidden header rows. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {QuickFlow}=await import(pathToFileURL(path.resolve(__dirname,'..','frontend','quick-flow.js')).href);
 const sheet=tables=>({name:'양식',title:'양식',lead:'안내 문장',tables,notes:['주석 문장']});
 const draw=(sheets,tab=0)=>QuickFlow.prototype.excelPreviewPanel.call({excelPreview:{sheets},excelTab:tab});

 // a form table: no dark header row, label cells, a value merged across three columns, a block merged over two rows
 const form={heading:'가. 조사 개요',columns:['','','',''],header:false,bordered:true,labels:[0],label_rows:[],label_cells:[[1,2]],widths:[22,40,22,40],
  merges:[[0,1,0,3],[1,3,2,3]],rows:[['조사 구분','☑ 정기조사\n☐ 최초조사','',''],['조사부서명','팀','작업공정명','입력 필요'],['작업명','상자 들기','','']]};
 let html=draw([sheet([form])]);
 assert.ok(!html.includes('<thead>'),'a form table has no header row');
 assert.match(html,/class="quick-sheet form"/);
 assert.match(html,/<td class="label">조사 구분<\/td>/,'the first column holds label cells');
 assert.match(html,/<td class="label">작업공정명<\/td>/,'a single cell can be a label too');
 assert.match(html,/<td class=""[^>]*colspan="3">☑ 정기조사<br>☐ 최초조사<\/td>/,'a value merged over three columns is drawn once with a colspan');
 assert.match(html,/<td class="missing" rowspan="2">입력 필요<\/td>/,'a block merged over two rows keeps its highlight and is drawn once with a rowspan');
 const rows=html.split('<tr>').slice(1);
 assert.equal(rows.length,3);
 assert.equal((rows[0].match(/<td/g)||[]).length,2,'the cells a merge covers are not drawn again');
 assert.equal((rows[1].match(/<td/g)||[]).length,4);
 assert.equal((rows[2].match(/<td/g)||[]).length,3,'the cell the row-merge covers is skipped');
 assert.match(html,/<h4 class="quick-sheet-heading">가\. 조사 개요<\/h4>/);

 // an ordinary table keeps its dark header; a table with many columns lets the header wrap; header text may have line breaks
 const matrix={heading:null,columns:['작업\n(단위작업)',...Array.from({length:11},(_,i)=>`기준 ${i+1}\n(${i+1}호)`),'판정'],bordered:true,labels:[0],label_rows:[0],widths:[],
  rows:[['기준','a','b','c','d','e','f','g','h','i','j','k',''],['상자 들기','○','X','입력 필요','검토 필요','','','','','','','','부담작업']]};
 html=draw([sheet([matrix])]);
 assert.match(html,/<thead><tr><th>작업<br>\(단위작업\)<\/th>/,'header line breaks become <br>');
 assert.match(html,/class="quick-sheet form wide"/);
 assert.match(html,/<td class="missing">입력 필요<\/td>/);
 assert.match(html,/<td class="review">검토 필요<\/td>/);
 assert.match(html,/<tr><td class="label">기준<\/td><td class="label">a<\/td>/,'a label row is drawn as labels');

 // a table without the form keys is drawn exactly as before
 const old={heading:null,columns:['작업','값'],rows:[['상자','240']],widths:[]};
 html=draw([sheet([old])]);
 assert.match(html,/<thead><tr><th>작업<\/th><th>값<\/th><\/tr><\/thead>/);
 assert.match(html,/class="quick-sheet"/);
 assert.ok(!/colspan|rowspan|class="label"/.test(html));
 assert.match(html,/<p class="quick-note">안내 문장<\/p>/);
 assert.match(html,/<p class="quick-note">주석 문장<\/p>/);
 assert.ok(!html.includes('form_sheets')&&!/이 조사에는/.test(html),'there is no longer a separate form-sheet sentence');

 // tabs: one per sheet, the chosen one is selected
 html=draw([sheet([old]),{...sheet([old]),name:'둘째'}],1);
 assert.match(html,/aria-selected="true" class="selected" data-quick="excel-tab" data-tab="1">둘째<\/button>/);
 console.log('PASS the Excel preview draws form-style tables (labels, merges, no header), ordinary tables as before');
})().catch(error=>{console.error('FAIL',error&&error.stack||error);process.exit(1);});
