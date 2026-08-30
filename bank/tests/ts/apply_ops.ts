import { applyOps } from "./solution";

function hit(ops: string[], expect: { A: number; B: number; C: number }): number {
  try {
    const got = applyOps(ops);
    return got.A === expect.A && got.B === expect.B && got.C === expect.C ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit([], { A: 0, B: 0, C: 0 });
n += hit(["+ A 3"], { A: 3, B: 0, C: 0 });
n += hit(["+ A 2", "- A 5"], { A: 2, B: 0, C: 0 });
n += hit(["+ A 4", "> A B"], { A: 0, B: 4, C: 0 });
n += hit(["+ C 1", "? C"], { A: 1, B: 0, C: 0 });
n += hit(["+ B 2", "? B", "? B"], { A: 0, B: 0, C: 2 });
console.log(`POINTS ${n}/6`);
