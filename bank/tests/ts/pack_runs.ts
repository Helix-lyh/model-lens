import { packRuns } from "./solution";

function hit(xs: number[], expect: Array<[number, number]>): number {
  try {
    return JSON.stringify(packRuns(xs)) === JSON.stringify(expect) ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit([], []);
n += hit([7], [[7, 1]]);
n += hit([1, 1, 1, 2, 2], [[1, 3], [2, 2]]);
n += hit([3, 1, 1, 3], [[3, 1], [1, 2], [3, 1]]);
n += hit([0, 0, 0, 0], [[0, 4]]);
console.log(`POINTS ${n}/5`);
