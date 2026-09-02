import { applyTransactions } from "./solution";
function hit(initial:Record<string,number>, txns:any[], want:any):number { try{return JSON.stringify(applyTransactions(initial,txns))===JSON.stringify(want)?1:0}catch{return 0} }
let n=0;
n+=hit({},[],{state:{},statuses:{}});
n+=hit({a:0},[{id:"t1",begin:0,writes:{a:2},commit:1}],{state:{a:2},statuses:{t1:"COMMIT"}});
n+=hit({a:0},[{id:"t1",begin:0,writes:{a:2},commit:2},{id:"t2",begin:0,writes:{a:3},commit:1}],{state:{a:3},statuses:{t1:"ABORT",t2:"COMMIT"}});
n+=hit({a:0},[{id:"t1",begin:0,writes:{a:2},commit:1},{id:"t2",begin:0,writes:{a:3},commit:2}],{state:{a:2},statuses:{t1:"COMMIT",t2:"ABORT"}});
n+=hit({a:0,b:0},[{id:"x",begin:0,writes:{a:1},commit:1},{id:"y",begin:0,writes:{b:2},commit:2}],{state:{a:1,b:2},statuses:{x:"COMMIT",y:"COMMIT"}});
n+=hit({a:1},[{id:"late",begin:1,writes:{a:9},commit:3},{id:"early",begin:0,writes:{a:4},commit:2}],{state:{a:9},statuses:{late:"COMMIT",early:"COMMIT"}});
console.log(`POINTS ${n}/6`);
