import { parseBadge } from "./solution";

function hit(raw: string, expect: [number, number, number, number] | null): number {
  try {
    return JSON.stringify(parseBadge(raw)) === JSON.stringify(expect) ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit("24#08.30+2", [2024, 8, 30, 2]);
n += hit("00#01.01+0", [2000, 1, 1, 0]);
n += hit("24#13.01+1", null);
n += hit("24/08.30+2", null);
n += hit("23#02.29+1", null);
console.log(`POINTS ${n}/5`);
