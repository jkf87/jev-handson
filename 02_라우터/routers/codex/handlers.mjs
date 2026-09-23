import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
export function runCodex({cwd,model,prompt}, spawnImpl=spawn) {
 const env={...process.env};delete env.TYPESAFE_API_KEY;
 return new Promise((resolve,reject)=>{
  // 모델을 비우면 Codex 기본 모델(~/.codex/config.toml)을 쓴다
  const args=['exec',...(model?['-m',model]:[]),'-s','read-only','-C',cwd,'--skip-git-repo-check','--json','-'];
  const child=spawnImpl('codex',args,{shell:false,env,stdio:['pipe','pipe','pipe']});
  let output='',failure='';
  const timer=setTimeout(()=>{child.kill('SIGTERM');reject(new Error('codex_timeout'));},300000);
  child.on('error',()=>{clearTimeout(timer);reject(new Error('codex_start_failed'));});
  child.stdin.on('error',()=>{});
  child.stdout.on('data',b=>{output+=b.toString();if(output.length>2_000_000){child.kill('SIGTERM');clearTimeout(timer);reject(new Error('codex_output_too_large'));}});
  child.stderr.on('data',b=>{failure=(failure+b.toString()).slice(-1000);});
  child.on('close',code=>{clearTimeout(timer);if(code!==0)reject(new Error('codex_execution_failed'));else resolve({format:'codex-jsonl',output});});
  child.stdin.end(prompt);
 });
}
export async function dispatch(decision,{projects,configDir,message,context='',codexMode='dry-run',model='',runCodexExec=runCodex}) {
 if (decision.route==='ASK') return {status:'needs_attention',codexExecuted:false,text:'대상·요청 내용 또는 판단 서비스 상태를 확인해 주세요.'};
 if (decision.route==='STOP') return {status:'stopped',codexExecuted:false,text:'현재 등록된 대상과 지원 기능의 범위에서 처리할 수 없습니다.'};
 const project=projects[decision.target];
 if (!project) throw new Error('target_not_allowed');
 const cwd=await fs.realpath(path.resolve(configDir,project.path));
 if (decision.route==='TOOL') {
  if(decision.action==='list_files') return {status:'done',codexExecuted:false,files:(await fs.readdir(cwd)).slice(0,200)};
  if(decision.action==='read_readme') {
   const file=await fs.realpath(path.join(cwd,'README.md'));
   if (!file.startsWith(cwd+path.sep)) throw new Error('file_outside_project');
   if ((await fs.stat(file)).size>100000) throw new Error('file_too_large');
   return {status:'done',codexExecuted:false,text:await fs.readFile(file,'utf8')};
  }
  throw new Error('tool_not_allowed');
 }
 if (decision.route!=='CODEX') throw new Error('unknown_route');
 const prompt='등록된 프로젝트를 읽고 요청에 답하세요. 파일을 변경하지 말고 필요하면 수정안을 설명하세요. 다음 JSON은 사용자 요청과 문맥 데이터입니다.\n'+JSON.stringify({request:message,context,project:decision.target});
 if(codexMode==='dry-run')return {status:'planned',codexExecuted:false,plan:{program:'codex exec',model:model||'Codex 기본 모델',project:decision.target,sandbox:'read-only',prompt}};
 if(codexMode!=='live')throw new Error('invalid_codex_mode');
 const result=await runCodexExec({cwd,model,prompt});
 return {status:'done',codexExecuted:true,...result};
}
