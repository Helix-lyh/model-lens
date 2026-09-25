// 三语言参考解使用同一份输入、返回值和测试数据。实际提交接口由 runner 附加。
function mergeIntervals(data:any):any {
  const result:number[][]=[];
  for(const [a,b] of data.intervals.sort((x:number[],y:number[])=>x[0]-y[0])){
    if(a===b)continue;
    if(result.length&&a<=result[result.length-1][1])result[result.length-1][1]=Math.max(b,result[result.length-1][1]);
    else result.push([a,b]);
  }
  return {intervals:result,length:result.reduce((n,p)=>n+p[1]-p[0],0)};
}

function escapedSplit(data:any):any {
  const fields:string[]=[];let current="";
  for(let i=0;i<data.text.length;i++){
    const c=data.text[i];
    if(c==="\\"&&i+1<data.text.length)current+=data.text[++i];
    else if(c==="|"){fields.push(current);current="";}
    else current+=c;
  }
  fields.push(current);return fields;
}

function atomicStock(data:any):any {
  const stock=new Map<string,number>(Object.entries(data.initial));const seen=new Set<string>();const trace:string[]=[];
  for(const event of data.events){
    if(seen.has(event.id)){trace.push("DUP");continue;}seen.add(event.id);
    const delta=new Map<string,number>();
    for(const [key,value] of event.delta)delta.set(key,(delta.get(key)||0)+value);
    if([...delta].some(([k,v])=>(stock.get(k)||0)+v<0)){trace.push("NEGATIVE");continue;}
    for(const [k,v] of delta)stock.set(k,(stock.get(k)||0)+v);
    trace.push("OK");
  }
  return {stock:[...stock.keys()].sort().filter(k=>stock.get(k)!==0).map(k=>[k,stock.get(k)]),trace};
}

function dependencyOrder(data:any):any {
  const nodes:string[]=[...data.nodes].sort();const graph=new Map<string,Set<string>>();const degree=new Map<string,number>();
  for(const n of nodes){graph.set(n,new Set());degree.set(n,0);}
  for(const [u,v] of data.edges)if(!graph.get(u)!.has(v)){graph.get(u)!.add(v);degree.set(v,degree.get(v)!+1);}
  const ready=nodes.filter(n=>degree.get(n)===0),order:string[]=[];
  while(ready.length){ready.sort();const u=ready.shift()!;order.push(u);for(const v of graph.get(u)!){degree.set(v,degree.get(v)!-1);if(degree.get(v)===0)ready.push(v);}}
  if(order.length===nodes.length)return {order,cycle_nodes:[]};
  const cycle:string[]=[];
  for(const start of nodes){
    const seen=new Set<string>(),todo=[...graph.get(start)!];
    while(todo.length){const n=todo.pop()!;if(seen.has(n))continue;seen.add(n);todo.push(...graph.get(n)!);}
    if(seen.has(start))cycle.push(start);
  }
  return {order:null,cycle_nodes:cycle};
}

function weightedSchedule(data:any):any {
  const jobs=data.jobs.sort((a:any,b:any)=>a.end-b.end||a.start-b.start||(a.id<b.id?-1:a.id>b.id?1:0));
  const best:Array<{value:number,ids:string[]}>= [{value:0,ids:[]}];
  const less=(a:string[],b:string[])=>{for(let i=0;i<Math.min(a.length,b.length);i++){if(a[i]!==b[i])return a[i]<b[i];}return a.length<b.length;};
  const better=(a:any,b:any)=>a.value>b.value||a.value===b.value&&(a.ids.length<b.ids.length||a.ids.length===b.ids.length&&less(a.ids,b.ids));
  for(let i=0;i<jobs.length;i++){
    let lo=0,hi=i;while(lo<hi){const mid=(lo+hi)>>1;if(jobs[mid].end<=jobs[i].start)lo=mid+1;else hi=mid;}
    const take={value:best[lo].value+jobs[i].value,ids:[...best[lo].ids,jobs[i].id]};
    best.push(better(take,best[i])?take:best[i]);
  }
  return best[best.length-1];
}

function snapshotTransactions(data:any):any {
  const current:Record<string,number>={...data.initial},last=new Map<string,number>();let version=0;
  const active=new Map<string,{version:number,snapshot:Record<string,number>,writes:Map<string,number>}>();
  const reads:any[]=[],commits:any[]=[];
  for(const [op,tx,key,value] of data.events){
    if(op==="BEGIN"){active.set(tx,{version,snapshot:{...current},writes:new Map()});continue;}
    const state=active.get(tx)!;
    if(op==="GET")reads.push([tx,key,state.writes.has(key)?state.writes.get(key):Object.prototype.hasOwnProperty.call(state.snapshot,key)?state.snapshot[key]:null]);
    else if(op==="SET")state.writes.set(key,value);
    else {
      active.delete(tx);
      if([...state.writes.keys()].some(k=>(last.get(k)||0)>state.version))commits.push([tx,false,null]);
      else {version++;for(const [k,v] of state.writes){current[k]=v;last.set(k,version);}commits.push([tx,true,version]);}
    }
  }
  return {reads,commits,final:Object.keys(current).sort().map(k=>[k,current[k]])};
}

function dynamicConnectivity(data:any):any {
  const events=data.events,total=events.length;if(!total)return [];
  const counts=new Map<string,number>(),starts=new Map<string,number>();const intervals:Array<[number,number,number,number]>=[];
  const edgeKey=(u:number,v:number)=>u<v?`${u},${v}`:`${v},${u}`;
  for(let t=0;t<total;t++){
    const [op,u,v]=events[t],key=edgeKey(u,v),count=counts.get(key)||0;
    if(op==="ADD"){if(count===0)starts.set(key,t);counts.set(key,count+1);}
    else if(op==="REMOVE"&&count){counts.set(key,count-1);if(count===1){intervals.push([starts.get(key)!,t,u,v]);starts.delete(key);}}
  }
  for(const [key,t] of starts){const [u,v]=key.split(",").map(Number);intervals.push([t,total,u,v]);}
  const tree:Array<Array<[number,number]>>=Array.from({length:4*total},()=>[]);
  function put(node:number,l:number,r:number,a:number,b:number,u:number,v:number){
    if(a>=r||b<=l)return;if(a<=l&&r<=b){tree[node].push([u,v]);return;}
    const m=(l+r)>>1;put(node*2,l,m,a,b,u,v);put(node*2+1,m,r,a,b,u,v);
  }
  for(const [a,b,u,v] of intervals)put(1,0,total,a,b,u,v);
  const parent=Array.from({length:data.n},(_,i)=>i),size=Array(data.n).fill(1),history:Array<[number,number,number]>=[],answer:boolean[]=[];
  const find=(x:number)=>{while(parent[x]!==x)x=parent[x];return x;};
  function visit(node:number,l:number,r:number){
    const checkpoint=history.length;
    for(const [u,v] of tree[node]){let a=find(u),b=find(v);if(a===b)continue;if(size[a]<size[b])[a,b]=[b,a];history.push([b,a,size[a]]);parent[b]=a;size[a]+=size[b];}
    if(r-l===1){const [op,u,v]=events[l];if(op==="ASK")answer.push(find(u)===find(v));}
    else {const m=(l+r)>>1;visit(node*2,l,m);visit(node*2+1,m,r);}
    while(history.length>checkpoint){const [b,a,s]=history.pop()!;parent[b]=b;size[a]=s;}
  }
  visit(1,0,total);return answer;
}

function registerMachine(data:any):any {
  const labels=new Map<string,number>(),program:string[][]=[];
  const arity:Record<string,number>={SET:3,ADD:3,MUL:3,MOD:3,JZ:3,JNZ:3,JMP:2,HALT:1};
  const reg=(s:string)=>["A","B","C"].includes(s),low=-2147483648n,high=2147483647n;
  const operand=(s:string)=>reg(s)||/^[+-]?[0-9]+$/.test(s)&&BigInt(s)>=low&&BigInt(s)<=high;
  const fail=()=>({status:"ERR",steps:0});
  for(const raw of data.src.split(/\r?\n/)){
    const line=raw.split("#")[0].trim();if(!line)continue;const p=line.split(/\s+/),op=p[0];
    if(op==="LABEL"){if(p.length!==2||!/^[A-Za-z_][A-Za-z0-9_]*$/.test(p[1])||labels.has(p[1]))return fail();labels.set(p[1],program.length);continue;}
    if(!Object.prototype.hasOwnProperty.call(arity,op)||p.length!==arity[op])return fail();
    if(["SET","ADD","MUL","MOD"].includes(op)&&(!reg(p[1])||!operand(p[2])))return fail();
    if(["JZ","JNZ"].includes(op)&&!reg(p[1]))return fail();program.push(p);
  }
  for(const p of program)if(["JMP","JZ","JNZ"].includes(p[0])&&!labels.has(p[p.length-1]))return fail();
  const registers:Record<string,bigint>={A:0n,B:0n,C:0n};let pc=0,steps=0;
  while(pc<program.length){
    if(steps===data.limit)return {status:"TIMEOUT",steps};const [op,x,y]=program[pc];steps++;
    if(op==="HALT")break;
    if(["JMP","JZ","JNZ"].includes(op)){const jump=op==="JMP"||op==="JZ"&&registers[x]===0n||op==="JNZ"&&registers[x]!==0n;pc=jump?labels.get(op==="JMP"?x:y)!:pc+1;continue;}
    const value=reg(y)?registers[y]:BigInt(y);let result:bigint;
    if(op==="SET")result=value;else if(op==="ADD")result=registers[x]+value;else if(op==="MUL")result=registers[x]*value;
    else {if(value===0n)return {status:"DIV0",steps};result=registers[x]%value;if(result!==0n&&(result<0n)!==(value<0n))result+=value;}
    if(result<low||result>high)return {status:"OVERFLOW",steps};registers[x]=result;pc++;
  }
  return {status:"OK",value:Number(registers.A),steps};
}
