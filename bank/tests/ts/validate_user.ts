import { validateUser } from "./solution";

function hit(obj: Record<string, unknown>, check: (got: string[]) => boolean): number {
  try {
    return check(validateUser(obj)) ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit({ name: "ann", age: 20 }, (got) => got.length === 0);
n += hit({ name: "", age: 20 }, (got) => got.includes("name"));
n += hit({ name: "ann", age: 200 }, (got) => got.includes("age"));
n += hit({ name: "ann" }, (got) => got.includes("age"));
n += hit({ age: 3 }, (got) => got.includes("name"));
console.log(`POINTS ${n}/5`);
