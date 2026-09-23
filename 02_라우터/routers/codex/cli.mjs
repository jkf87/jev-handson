import fs from 'node:fs/promises';
const cases=JSON.parse(await fs.readFile(new URL('./config/cases.json',import.meta.url),'utf8'));
const [option,value]=process.argv.slice(2);
const selected=option==='--all'?cases:option==='--case'?cases.filter(x=>x.id===value):[{message:process.argv.slice(2).join(' ')}];
if(!selected.length||!selected[0].message){console.error('node cli.mjs --case list_docs | --all | "요청 내용"');process.exit(1);}
for(const item of selected){
 try{
  const response=await fetch(`http://127.0.0.1:${process.env.PORT??8427}/route`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:item.message}),signal:AbortSignal.timeout(330000)});
  const result=await response.json();
  console.log(JSON.stringify({case:item.id??'custom',expected:item.expected??null,...result},null,2));
  if(!response.ok||(item.expected&&result.route!==item.expected))process.exitCode=1;
 }catch{console.error('라우터 서비스 주소·실행 상태를 확인하세요.');process.exitCode=1;}
}
