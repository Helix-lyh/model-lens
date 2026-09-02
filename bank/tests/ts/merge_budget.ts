import { mergeBudget } from "./solution";
function hit(xs:Array<[number,number]>, b:number, want:any):number { try { return JSON.stringify(mergeBudget(xs,b))===JSON.stringify(want)?1:0; } catch { return 0; } }
let n=0;
n+=hit([],0,{ok:true,intervals:[],reason:"empty"});
n+=hit([[1,3],[3,5]],5,{ok:true,intervals:[[1,5]],reason:"empty"});
n+=hit([[5,7],[1,2],[2,4]],7,{ok:true,intervals:[[1,7]],reason:"empty"});
n+=hit([[1,3],[10,10]],3,{ok:false,intervals:[],reason:"budget_exceeded"});
n+=hit([[3,2]],10,{ok:false,intervals:[],reason:"invalid"});
n+=hit([[0,0],[-2,-1]],3,{ok:true,intervals:[[-2,0]],reason:"empty"});
console.log(`POINTS ${n}/6`);
