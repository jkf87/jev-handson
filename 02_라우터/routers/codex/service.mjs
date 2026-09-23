import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createJudge} from './judge.mjs';
import {selectRoute} from './policy.mjs';
import {dispatch} from './handlers.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
export async function createRouter({mode=process.env.JEV_MODE??'mock',codexMode=process.env.CODEX_MODE??'dry-run',judge:providedJudge,runCodexExec,log=()=>{}}={}) {
 const configDir=path.join(root,'config');
 const projects=JSON.parse(await fs.readFile(path.join(configDir,'projects.json'),'utf8'));
 const cases=JSON.parse(await fs.readFile(path.join(configDir,'cases.json'),'utf8'));
 const threshold=Number(process.env.ROUTE_CONFIDENCE??0.8);
 if(!Number.isFinite(threshold)||threshold<0||threshold>1)throw new Error('Invalid confidence policy');
 if(!['dry-run','live'].includes(codexMode))throw new Error('Invalid Codex mode');
 const judge=providedJudge??createJudge({projects,cases,mode,apiKey:process.env.TYPESAFE_API_KEY,model:process.env.TYPESAFE_MODEL??'jev-latest'});
 return async function route(message,context='') {
  if(typeof message!=='string'||!message.trim()||message.length>10000||typeof context!=='string'||context.length>20000)throw new Error('invalid_input');
  const requestId=randomUUID();let decision,judgment={source:mode==='mock'?'mock-fixture':'jev-api',model:null};
  try{judgment=await judge(message,context);decision=selectRoute(judgment.answers,projects,threshold);}
  catch{decision={route:'ASK',reason:'judge_service_error',action:null,target:null};}
  let result;
  try{result=await dispatch(decision,{projects,configDir,message,context,codexMode,model:process.env.CODEX_MODEL,runCodexExec});}
  catch{result={status:'handler_error',codexExecuted:null,text:'처리 함수의 실행 상태를 확인해 주세요. 자동 재실행하지 않습니다.'};}
  const summary={requestId,mode,judgmentSource:judgment.source,model:judgment.model,...decision,codexExecuted:result.codexExecuted,status:result.status};
  log(summary);return {...summary,result};
 };
}
export function createServer(route) {
 return http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json; charset=utf-8');
  const send=(status,value)=>{res.writeHead(status);res.end(JSON.stringify(value));};
  if(req.headers.origin)return send(403,{error:'browser_origin_not_supported'});
  if(req.method==='GET'&&req.url==='/health')return send(200,{status:'ok'});
  if(req.method!=='POST'||req.url!=='/route')return send(404,{error:'not_found'});
  if(!req.headers['content-type']?.includes('application/json'))return send(415,{error:'json_required'});
  try{
   const chunks=[];let size=0;
   for await (const chunk of req){size+=chunk.length;if(size>65536)return send(413,{error:'request_too_large'});chunks.push(chunk);}
   const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
   send(200,await route(input.message,input.context??''));
  }catch{send(400,{error:'invalid_request'});}
 });
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 const route=await createRouter({log:record=>console.log(JSON.stringify(record))});
 const server=createServer(route);server.on('error',e=>{console.error('Server failed:',e.code);process.exitCode=1;});
 server.listen(Number(process.env.PORT??8427),'127.0.0.1',()=>console.log(`Router ready on localhost; JEV_MODE=${process.env.JEV_MODE??'mock'} CODEX_MODE=${process.env.CODEX_MODE??'dry-run'}`));
}
