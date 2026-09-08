import { orderEvents } from "./solution";
function sameArr(a:string[], b:string[]):boolean {
  return a.length===b.length && a.every((x,i)=>x===b[i]);
}
function hit(events:Array<[string,string]>, want:any):number {
  try {
    const got=orderEvents(events);
    return (got.state===want.state && sameArr(got.applied||[], want.applied||[]) && sameArr(got.rejected||[], want.rejected||[]))?1:0;
  } catch { return 0; }
}
let n=0;
n+=hit([],{state:"CREATED",applied:[],rejected:[]});
n+=hit([["p","PAY"],["s","SHIP"],["d","DELIVER"]],{state:"DELIVERED",applied:["p","s","d"],rejected:[]});
n+=hit([["c","CANCEL"],["p","PAY"]],{state:"CANCELLED",applied:["c"],rejected:["p"]});
n+=hit([["p","PAY"],["p","PAY"]],{state:"PAID",applied:["p"],rejected:[]});
n+=hit([["s","SHIP"],["p","PAY"],["r","REFUND"]],{state:"REFUNDED",applied:["p","r"],rejected:["s"]});
n+=hit([["p","PAY"],["r","REFUND"],["s","SHIP"]],{state:"REFUNDED",applied:["p","r"],rejected:["s"]});
n+=hit([["p","PAY"],["s","SHIP"],["r","REFUND"],["d","DELIVER"]],{state:"REFUNDED",applied:["p","s","r"],rejected:["d"]});
n+=hit([["p","PAY"],["c","CANCEL"]],{state:"PAID",applied:["p"],rejected:["c"]});
n+=hit([["p","PAY"],["s","SHIP"],["d","DELIVER"],["r","REFUND"]],{state:"DELIVERED",applied:["p","s","d"],rejected:["r"]});
console.log(`POINTS ${n}/9`);
