import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {EventEmitter} from 'node:events';
import {createRouter} from '../service.mjs';
import {createJudge,fixtureAnswer} from '../judge.mjs';
import {buildQuestions} from '../questions.mjs';
import {selectRoute} from '../policy.mjs';
import {runCodex} from '../handlers.mjs';
const projects=JSON.parse(await fs.readFile(new URL('../config/projects.json',import.meta.url),'utf8'));
const cases=JSON.parse(await fs.readFile(new URL('../config/cases.json',import.meta.url),'utf8'));
const questions=buildQuestions(projects);
const answers=(action,target)=>({action:fixtureAnswer(action,questions.action.criteria),target:fixtureAnswer(target,questions.target.criteria)});
test('mock cases exercise every route without spawning Codex',async()=>{
 let calls=0;const router=await createRouter({mode:'mock',codexMode:'dry-run',runCodexExec:async()=>{calls++;throw Error('must not run');}});
 for(const item of cases){const r=await router(item.message);assert.equal(r.route,item.expected);assert.equal(r.codexExecuted,false);assert.equal(r.judgmentSource,'mock-fixture');}
 assert.equal(calls,0);
});
test('TOOL returns actual project contents',async()=>{
 const router=await createRouter();const list=await router(cases[0].message);assert.ok(list.result.files.includes('README.md'));
 const read=await router(cases[1].message);assert.match(read.result.text,/라우터 실습 문서/);
});
test('only CODEX reaches the injected execution adapter',async()=>{
 const original=process.env.CODEX_MODEL;process.env.CODEX_MODEL='test-model';let calls=0;
 try{const router=await createRouter({mode:'mock',codexMode:'live',runCodexExec:async plan=>{calls++;assert.ok(path.isAbsolute(plan.cwd));assert.equal(plan.model,'test-model');return {output:'fake execution for test'};}});
 for(const item of cases)await router(item.message);assert.equal(calls,cases.filter(c=>c.expected==='CODEX').length);
 }finally{if(original===undefined)delete process.env.CODEX_MODEL;else process.env.CODEX_MODEL=original;}
});
test('judge failure never escalates automatically to Codex',async()=>{
 let calls=0;const router=await createRouter({judge:async()=>{throw Error('secret detail');},codexMode:'live',runCodexExec:async()=>{calls++;}});
 const r=await router('요청');assert.equal(r.route,'ASK');assert.equal(r.reason,'judge_service_error');assert.equal(calls,0);assert.ok(!JSON.stringify(r).includes('secret detail'));
});
test('unused target does not block a clear STOP or ASK',()=>{
 assert.equal(selectRoute({action:answers('unsupported','none').action},projects).route,'STOP');
 assert.equal(selectRoute({action:answers('clarify','none').action},projects).route,'ASK');
});
test('malformed or ambiguous answers cannot execute',()=>{
 const a=answers('list_files','docs');a.target.confidence=0.1;assert.equal(selectRoute(a,projects).route,'ASK');
 const b=answers('generate','app');b.target.choice='not-registered';assert.equal(selectRoute(b,projects).route,'ASK');
 const c=answers('generate','app');c.action.probabilities.generate=2;assert.equal(selectRoute(c,projects).route,'ASK');
 assert.equal(selectRoute(answers('generate','none'),projects).route,'ASK');
});
test('live adapter sends both questions once, with no project paths in state',async()=>{
 let calls=0;const judge=createJudge({projects,mode:'live',apiKey:'test-not-secret',fetchImpl:async(url,options)=>{
 calls++;assert.equal(url,'https://api.typesafe.ai/v1/systemone');assert.equal(options.method,'POST');const body=JSON.parse(options.body);assert.deepEqual(Object.keys(body.questions),['action','target']);assert.deepEqual(body.questions,questions);assert.equal(body.state.message,'test');assert.ok(!JSON.stringify(body.state).includes('../workspaces'));
 return {ok:true,json:async()=>({model:'test-only',answers:answers('generate','app')})};}});
 const r=await judge('test');assert.equal(calls,1);assert.equal(r.source,'jev-api');assert.equal(r.model,'test-only');
});
test('Codex invocation uses argv and stdin, never a shell',async()=>{
 let called,stdin;const fake=(program,args,opts)=>{called={program,args,opts};const p=new EventEmitter();p.stdout=new EventEmitter();p.stderr=new EventEmitter();p.stdin=new EventEmitter();p.stdin.end=data=>{stdin=data;queueMicrotask(()=>{p.stdout.emit('data',Buffer.from('fake'));p.emit('close',0);});};p.kill=()=>{};return p;};
 const prompt='literal $(not-a-command)';const result=await runCodex({cwd:process.cwd(),model:'test-model',prompt},fake);
 assert.equal(called.opts.shell,false);assert.equal(called.program,'codex');assert.ok(called.args.includes('read-only'));assert.equal(stdin,prompt);assert.equal(result.output,'fake');assert.ok(!Object.hasOwn(called.opts.env,'TYPESAFE_API_KEY'));
});
