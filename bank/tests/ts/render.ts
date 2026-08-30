import { render } from "./solution";

function hit(tpl: string, vars: Record<string, string>, want: string): number {
  try {
    return render(tpl, vars) === want ? 1 : 0;
  } catch {
    return 0;
  }
}

let n = 0;
n += hit("hello", {}, "hello");
n += hit("hi {name}!", { name: "Tom" }, "hi Tom!");
n += hit("{a}+{b}", { a: "1" }, "1+{b}");
n += hit("{{name}}", { name: "X" }, "{name}");
n += hit("{a b} { {}", {}, "{a b} { {}");
n += hit("{x}{{y}}{z}", { x: "1", z: "2" }, "1{y}2");
n += hit("{{{name}}}", { name: "Tom" }, "{Tom}");
n += hit("{{y}}", { y: "Y" }, "{y}");
console.log(`POINTS ${n}/8`);
