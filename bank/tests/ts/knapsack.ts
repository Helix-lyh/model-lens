import { boundedKnapsack } from "./solution";
function sameIdx(a:number[], b:number[]):boolean {
  return a.length===b.length && a.every((x,i)=>x===b[i]);
}
function hit(xs:Array<[number,number]>, c:number, want:any):number {
  try {
    const got=boundedKnapsack(xs,c);
    return (got.value===want.value && got.weight===want.weight && sameIdx(got.indices||[], want.indices||[]))?1:0;
  } catch { return 0; }
}
let n=0;
n+=hit([],5,{value:0,weight:0,indices:[]});
n+=hit([[2,3]],1,{value:0,weight:0,indices:[]});
n+=hit([[4,7],[5,9],[6,10],[3,5]],10,{value:17,weight:10,indices:[0,2]});
n+=hit([[2,5],[2,5]],2,{value:5,weight:2,indices:[0]});
n+=hit([[1,-1],[2,4],[3,4]],3,{value:4,weight:2,indices:[1]});
n+=hit([[1,2],[2,4],[3,6]],3,{value:6,weight:3,indices:[0,1]});
n+=hit([[5,10],[1,10]],5,{value:10,weight:5,indices:[0]});
function oracle(xs:Array<[number,number]>, c:number):any {
 let best:any={value:0,weight:0,indices:[]};
 for(let mask=0;mask<(1<<xs.length);mask++){
  let w=0,v=0,ix:number[]=[];
  xs.forEach((x,i)=>{if(mask&(1<<i)){w+=x[0];v+=x[1];ix.push(i)}});
  if(w<=c&&(v>best.value||(v===best.value&&ix.join(',')<best.indices.join(',')))) best={value:v,weight:w,indices:ix};
 }
 return best;
}
for(let seed=0;seed<12;seed++){const xs:Array<[number,number]>=[];for(let i=0;i<5;i++)xs.push([(seed*7+i*3)%6+1,(seed*11+i*5)%13-3]);const c=(seed*5)%13;n+=hit(xs,c,oracle(xs,c));}
console.log(`POINTS ${n}/19`);
