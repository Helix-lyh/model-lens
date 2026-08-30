import { tagScores } from "./solution";

function norm(m: Record<string, number>): string {
  return JSON.stringify(Object.entries(m).sort());
}

function hit(items: string[], want: Record<string, number>): number {
  try {
    return norm(tagScores(items)) === norm(want) ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit([], {});
n += hit(["a:1", "b:2", "a:3"], { a: 4, b: 2 });
n += hit(["a:-3", "a:5"], { a: 2 });
n += hit(["x", ":5", "a:one", "a:1:2"], {});
n += hit(["cpu:10", "bad", "cpu:-4", "mem:7", ":9"], { cpu: 6, mem: 7 });
n += hit(["a:+5", "a: 1", "a:1_000", "ok:-2"], { ok: -2 });
console.log(`POINTS ${n}/6`);
