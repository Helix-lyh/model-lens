import { planTasks } from "./solution";

function hit(tasks: string[], deps: Array<[string, string]>, want: string[] | null): number {
  try {
    const got = planTasks(tasks, deps);
    if (want === null || got === null) {
      return want === got ? 1 : 0;
    }
    return JSON.stringify(got) === JSON.stringify(want) ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit(["c", "a", "b"], [], ["a", "b", "c"]);
n += hit(["a", "b", "c"], [["a", "b"], ["b", "c"]], ["c", "b", "a"]);
n += hit(["d", "b", "c", "a"], [["b", "a"], ["c", "a"], ["d", "b"], ["d", "c"]], ["a", "b", "c", "d"]);
n += hit(["a", "b"], [["a", "b"], ["b", "a"]], null);
n += hit(["a", "b"], [["b", "a"], ["b", "a"]], ["a", "b"]);
n += hit(["t3", "t1", "x", "t2"], [["t2", "t1"], ["t3", "t2"], ["x", "t1"]], ["t1", "t2", "t3", "x"]);
console.log(`POINTS ${n}/6`);
