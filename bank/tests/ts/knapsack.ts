import { boundedKnapsack } from "./solution";
function hit(xs:Array<[number,number]>, c:number, want:any):number { try{return JSON.stringify(boundedKnapsack(xs,c))===JSON.stringify(want)?1:0}catch{return 0} }
let n=0;
n+=hit([],5,{value:0,weight:0,indices:[]});
n+=hit([[2,3]],1,{value:0,weight:0,indices:[]});
n+=hit([[4,7],[5,9],[6,10],[3,5]],10,{value:17,weight:10,indices:[0,2]});
n+=hit([[2,5],[2,5]],2,{value:5,weight:2,indices:[0]});
n+=hit([[1,-1],[2,4],[3,4]],3,{value:4,weight:2,indices:[1]});
n+=hit([[1,2],[2,4],[3,6]],3,{value:6,weight:3,indices:[0,1]});
console.log(`POINTS ${n}/6`);
