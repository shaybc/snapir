/** Render the operation planning views from shared call discovery results. */
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const [input, output, modules] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const packagePath = require.resolve('@oai/artifact-tool', modules ? {paths:[path.dirname(modules)]} : undefined);
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(packagePath).href);
const {graph, waves, relationships} = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();

function sheet(name, title, context, headers, rows, widths, tableName) {
  const item = workbook.worksheets.add(name);
  item.showGridLines = false;
  const last = String.fromCharCode(64 + headers.length);
  const end = Math.max(6, 5 + rows.length);
  item.getRange(`A1:${last}${end}`).format.font = {name:'Arial',size:11,color:'#243247'};
  item.getRange('A2').values = [[title]];
  item.getRange('A2').format.font = {size:16,bold:true};
  item.getRange('A3').values = [[context]];
  item.getRange('A3').format.font = {size:10,italic:true,color:'#58677B'};
  item.getRange(`A5:${last}5`).values = [headers];
  if(rows.length) item.getRange(`A6:${last}${5+rows.length}`).values = rows;
  const table = item.tables.add(`A5:${last}${end}`,true,tableName);
  table.showFilterButton = true;
  item.getRange(`A5:${last}5`).format = {fill:'#234568',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:32,horizontalAlignment:'center',verticalAlignment:'center'};
  item.getRange(`A6:${last}${end}`).format.verticalAlignment = 'center';
  widths.forEach((width,i)=> item.getRange(`${String.fromCharCode(65+i)}5:${String.fromCharCode(65+i)}${end}`).format.columnWidth=width);
  item.getRange(`A6:${last}${end}`).format.wrapText=true;
  item.getRange(`A6:${last}${end}`).format.autofitRows();
  item.freezePanes.freezeRows(5);
  return item;
}
const ordered=Object.keys(graph.operations).sort((a,b)=>(waves[a].wave ?? Infinity)-(waves[b].wave ?? Infinity)||a.localeCompare(b));
const plan=sheet('Migration Plan','Operation implementation order','Dependencies first. Cycles require coordinated implementation; blank waves have unresolved dependencies.',
  ['Build wave','Channel','Operation','Implement after (direct)','Cycle group','Issue'],
  ordered.map(key=>[waves[key].wave,graph.operations[key].channel,graph.operations[key].operation_id,waves[key].prerequisites.join('\n')||'None',waves[key].cycle_group||'None',waves[key].issue]),
  [15,18,32,62,45,45],'MigrationPlanTable');
plan.getRange(`A6:A${Math.max(6,ordered.length+5)}`).setNumberFormat('0');
const operations=sheet('Operations','Operation inventory','Counts are unique direct operation connections, not step counts or implementation effort.',
  ['Channel','Operation','Calls count','Callers count','Build wave','Cycle group'],
  Object.keys(graph.operations).sort().map(key=>[graph.operations[key].channel,graph.operations[key].operation_id,waves[key].calls_count,waves[key].callers_count,waves[key].wave,waves[key].cycle_group||'None']),
  [18,32,17,17,16,45],'OperationsTable');
operations.getRange(`C6:E${Math.max(6,ordered.length+5)}`).setNumberFormat('#,##0');
if(relationships) sheet('Relationships','Operation call evidence','Filter Caller or Called operation. Multiple call sites are retained as evidence.',
  ['Caller','Called operation','Invoking step','Mapper note'],
  graph.calls.map(call=>[call.caller,call.callee,call.step,call.note]),[42,42,32,62],'RelationshipsTable');
if(graph.issues.length) sheet('Issues','Unresolved operation relationships','Affected operations and their callers have no assigned build wave.',
  ['Operation','Step','Issue'],graph.issues.map(issue=>[issue.operation,issue.step,issue.detail]),[42,45,90],'IssuesTable');
workbook.recalculate();
const scan=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?',options:{useRegex:true,maxResults:10},maxChars:1500});
if(scan.ndjson.includes('"kind":"match"')) throw new Error(scan.ndjson);
// A preview is optional for automated callers, enabling visual QA without extra workbook variants.
if(process.env.OPERATION_REPORT_PREVIEW_DIR){
  for(const name of ['Migration Plan','Operations',...(relationships?['Relationships']:[]),...(graph.issues.length?['Issues']:[])]){
    const preview=await workbook.render({sheetName:name,range:name==='Relationships'?'A1:D12':name==='Issues'?'A1:C12':'A1:F12',scale:1,format:'png'});
    await fs.writeFile(path.join(process.env.OPERATION_REPORT_PREVIEW_DIR,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
  }
}
await (await SpreadsheetFile.exportXlsx(workbook)).save(output);
