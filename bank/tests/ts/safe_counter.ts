import { SafeCounter } from "./solution";

let n = 0;
try {
  const c = new SafeCounter();
  for (let i = 0; i < 1600; i++) {
    c.increment();
  }
  n += Number(c.value() === 1600);
} catch {
  /* keep n */
}
console.log(`POINTS ${n}/1`);
