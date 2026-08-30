import { FreezeBag } from "./solution";

let n = 0;
try {
  const bag = new FreezeBag(2);
  bag.put("a", 1);
  bag.put("b", 2);
  n += Number(bag.get("a") === 1);
  bag.freeze("a");
  bag.put("c", 3);
  n += Number(bag.get("a") === 1);
  n += Number(bag.get("b") === null);
  n += Number(bag.get("c") === 3);
} catch {
  /* keep n */
}
console.log(`POINTS ${n}/4`);
