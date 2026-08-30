import { cookText } from "./solution";

function sameVowels(got: Record<string, number>, want: Record<string, number>): boolean {
  const gk = Object.keys(got).sort();
  const wk = Object.keys(want).sort();
  if (gk.length !== wk.length) {
    return false;
  }
  return gk.every((k, i) => k === wk[i] && got[k] === want[k]);
}

function hit(
  s: string,
  expect: { vowels: Record<string, number>; squeezes: number; nums: number[] },
): number {
  try {
    const got = cookText(s);
    const numsOk = JSON.stringify(got.nums) === JSON.stringify(expect.nums);
    return sameVowels(got.vowels, expect.vowels) && got.squeezes === expect.squeezes && numsOk ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit("", { vowels: {}, squeezes: 0, nums: [] });
n += hit("book", { vowels: { o: 2 }, squeezes: 1, nums: [] });
n += hit("a12b3", { vowels: { a: 1 }, squeezes: 0, nums: [12, 3] });
n += hit("AAE", { vowels: { a: 2, e: 1 }, squeezes: 1, nums: [] });
n += hit("x7y", { vowels: {}, squeezes: 0, nums: [7] });
console.log(`POINTS ${n}/5`);
