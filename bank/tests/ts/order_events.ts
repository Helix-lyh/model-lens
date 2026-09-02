import { orderEvents } from "./solution";
function hit(events:Array<[string,string]>, want:any):number { try{return JSON.stringify(orderEvents(events))===JSON.stringify(want)?1:0}catch{return 0} }
let n=0;
n+=hit([],{state:"CREATED",applied:[],rejected:[]});
n+=hit([["p","PAY"],["s","SHIP"],["d","DELIVER"]],{state:"DELIVERED",applied:["p","s","d"],rejected:[]});
n+=hit([["c","CANCEL"],["p","PAY"]],{state:"CANCELLED",applied:["c"],rejected:["p"]});
n+=hit([["p","PAY"],["p","PAY"]],{state:"PAID",applied:["p"],rejected:[]});
n+=hit([["s","SHIP"],["p","PAY"],["r","REFUND"]],{state:"REFUNDED",applied:["p","r"],rejected:["s"]});
n+=hit([["p","PAY"],["r","REFUND"],["s","SHIP"]],{state:"REFUNDED",applied:["p","r"],rejected:["s"]});
n+=hit([["p","PAY"],["s","SHIP"],["r","REFUND"],["d","DELIVER"]],{state:"REFUNDED",applied:["p","s","r"],rejected:["d"]});
console.log(`POINTS ${n}/7`);
