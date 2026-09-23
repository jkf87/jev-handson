import {buildQuestions} from './questions.mjs';
export function fixtureAnswer(choice,criteria) {
 return {type:'choice',choice,confidence:1,probabilities:Object.fromEntries(Object.keys(criteria).map(k=>[k,k===choice?1:0]))};
}
export function createJudge({projects,cases=[],mode='mock',apiKey,model='jev-latest',baseUrl=process.env.TYPESAFE_BASE_URL||'https://api.typesafe.ai',fetchImpl=fetch}) {
 if (!['mock','live'].includes(mode)) throw new Error('JEV_MODE must be mock or live');
 const questions=buildQuestions(projects);
 return async function judge(message,context='') {
  if (mode==='mock') {
   const item=cases.find(c=>c.message===message)??{action:'clarify',target:'none'};
   return {model:'fixture-not-jev',source:'mock-fixture',answers:{action:fixtureAnswer(item.action,questions.action.criteria),target:fixtureAnswer(item.target,questions.target.criteria)}};
  }
  if (!apiKey && baseUrl.includes('api.typesafe.ai')) throw new Error('missing_typesafe_api_key');
  const response=await fetchImpl(`${baseUrl.replace(/\/$/,'')}/v1/systemone`,{
   method:'POST',signal:AbortSignal.timeout(15000),
   headers:{...(apiKey?{'Authorization':`Bearer ${apiKey}`}:{}),'Content-Type':'application/json','User-Agent':'jev-codex-router/1.0'},
   body:JSON.stringify({model,state:{message,context,projects:Object.fromEntries(Object.entries(projects).map(([k,v])=>[k,v.description]))},questions})
  });
  if (!response.ok) throw new Error(`jev_http_${response.status}`);
  const result=await response.json();
  return {model:result.model??model,source:'jev-api',answers:result.answers};
 };
}
