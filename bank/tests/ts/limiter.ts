import { SlidingLimiter } from "./solution";

function hit(limit: number, window: number, seq: number[], want: boolean[]): number {
  try {
    const lim = new SlidingLimiter(limit, window);
    for (let i = 0; i < seq.length; i++) {
      if (lim.allow(seq[i]) !== want[i]) {
        return 0;
      }
    }
    return 1;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit(2, 10, [1, 2, 3], [true, true, false]);
n += hit(2, 10, [1, 2, 11, 12, 12], [true, true, true, true, false]);
n += hit(1, 5, [0, 4, 5], [true, false, true]);
n += hit(1, 3, [1, 2, 3, 5], [true, false, false, true]);
n += hit(2, 1, [7, 7, 7], [true, true, false]);
n += hit(3, 4, [1, 2, 3, 4, 6], [true, true, true, false, true]);
console.log(`POINTS ${n}/6`);
