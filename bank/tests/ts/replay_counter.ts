import { replayCounter } from "./solution";
function hit(log: Array<[string,string,number]>, want: any): number {
  try { return JSON.stringify(replayCounter(log)) === JSON.stringify(want) ? 1 : 0; } catch { return 0; }
}
let n = 0;
n += hit([], {balance:0, accepted:[], rejected:[]});
n += hit([["a","credit",10],["b","debit",3]], {balance:7,accepted:["a","b"],rejected:[]});
n += hit([["a","credit",5],["a","credit",9]], {balance:5,accepted:["a"],rejected:["a"]});
n += hit([["x","debit",1]], {balance:0,accepted:[],rejected:["x"]});
n += hit([["a","credit",10],["b","debit",6],["c","refund",4]], {balance:8,accepted:["a","b","c"],rejected:[]});
n += hit([["a","credit",2],["c","refund",1],["b","debit",1],["c","refund",5]], {balance:1,accepted:["a","b"],rejected:["c","c"]});
n += hit([["a","credit",1],["b","debit",1],["c","refund",2]], {balance:0,accepted:["a","b"],rejected:["c"]});
console.log(`POINTS ${n}/7`);
