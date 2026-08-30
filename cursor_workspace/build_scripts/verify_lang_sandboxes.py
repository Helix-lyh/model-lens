"""Verify Go/TS bank tests against known-good solutions."""

from __future__ import annotations

from pathlib import Path

from src.bank import repo_root
from src.grade import run_go_sandbox, run_ts_sandbox

ROOT = repo_root()

GO = {
    "bank/tests/go/pack_runs_test.go": """
package solution
func PackRuns(xs []int) [][2]int {
    if len(xs) == 0 { return nil }
    out := [][2]int{}
    cur, cnt := xs[0], 1
    for i := 1; i < len(xs); i++ {
        if xs[i] == cur { cnt++ } else { out = append(out, [2]int{cur, cnt}); cur, cnt = xs[i], 1 }
    }
    return append(out, [2]int{cur, cnt})
}
""",
    "bank/tests/go/validate_user_test.go": """
package solution
func ValidateUser(obj map[string]any) []string {
    var err []string
    name, ok := obj["name"].(string)
    if !ok || name == "" { err = append(err, "name") }
    switch age := obj["age"].(type) {
    case int:
        if age < 0 || age > 120 { err = append(err, "age") }
    default:
        err = append(err, "age")
    }
    return err
}
""",
    "bank/tests/go/parse_badge_test.go": """
package solution
import "time"
func ParseBadge(s string) (int, int, int, int, bool) {
    if len(s) != 10 || s[2] != '#' || s[5] != '.' || s[8] != '+' { return 0,0,0,0,false }
    yy, mm, dd, n := s[0:2], s[3:5], s[6:8], s[9:10]
    for _, p := range []string{yy, mm, dd, n} {
        for _, c := range p { if c < '0' || c > '9' { return 0,0,0,0,false } }
    }
    y := 2000 + atoi2(yy)
    m := atoi2(mm)
    d := atoi2(dd)
    k := atoi2(n)
    if m < 1 || m > 12 || k > 9 { return 0,0,0,0,false }
    t := time.Date(y, time.Month(m), d, 0, 0, 0, 0, time.UTC)
    if t.Year() != y || int(t.Month()) != m || t.Day() != d { return 0,0,0,0,false }
    return y, m, d, k, true
}
func atoi2(s string) int { n := 0; for _, c := range s { n = n*10 + int(c-'0') }; return n }
""",
    "bank/tests/go/apply_ops_test.go": """
package solution
func ApplyOps(ops []string) map[string]int {
    bins := map[string]int{"A": 0, "B": 0, "C": 0}
    nxt := map[string]string{"A": "B", "B": "C", "C": "A"}
    for _, raw := range ops {
        parts := split(raw)
        if len(parts) == 0 { continue }
        switch parts[0] {
        case "+":
            bins[parts[1]] += atoi(parts[2])
        case "-":
            n := atoi(parts[2])
            if bins[parts[1]] >= n { bins[parts[1]] -= n }
        case ">":
            bins[parts[2]] += bins[parts[1]]
            bins[parts[1]] = 0
        case "?":
            x := parts[1]
            if bins[x] > 0 { bins[x]--; bins[nxt[x]]++ }
        }
    }
    return bins
}
func split(s string) []string {
    out := []string{}
    cur := ""
    for _, c := range s {
        if c == ' ' { if cur != "" { out = append(out, cur); cur = "" } } else { cur += string(c) }
    }
    if cur != "" { out = append(out, cur) }
    return out
}
func atoi(s string) int { n := 0; for _, c := range s { n = n*10 + int(c-'0') }; return n }
""",
    "bank/tests/go/cook_text_test.go": """
package solution
type CookResult struct { Vowels map[string]int; Squeezes int; Nums []int }
func CookText(s string) CookResult {
    vowels := map[string]int{}
    nums := []int{}
    squeezes := 0
    i := 0
    for i < len(s) {
        c := s[i]
        if c >= '0' && c <= '9' {
            n := 0
            for i < len(s) && s[i] >= '0' && s[i] <= '9' { n = n*10 + int(s[i]-'0'); i++ }
            nums = append(nums, n)
            continue
        }
        run := 1
        for i+run < len(s) && s[i+run] == c { run++ }
        low := c
        if c >= 'A' && c <= 'Z' { low = c + 32 }
        if low == 'a' || low == 'e' || low == 'i' || low == 'o' || low == 'u' {
            vowels[string(low)] += run
        }
        if isLetter(c) && run > 1 { squeezes += run - 1 }
        i += run
    }
    return CookResult{Vowels: vowels, Squeezes: squeezes, Nums: nums}
}
func isLetter(c byte) bool { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') }
""",
    "bank/tests/go/orders_sql_test.go": """
package solution
import "fmt"
func OrdersForUserSQL(userID int) string {
    return fmt.Sprintf("SELECT id, user_id, created_at, amount FROM orders WHERE user_id = %d ORDER BY created_at DESC LIMIT 20", userID)
}
""",
    "bank/tests/go/freeze_bag_test.go": """
package solution
type FreezeBag struct {
    cap int
    order []string
    vals map[string]int
    frozen map[string]bool
}
func NewFreezeBag(capacity int) *FreezeBag {
    return &FreezeBag{cap: capacity, vals: map[string]int{}, frozen: map[string]bool{}}
}
func (b *FreezeBag) touch(key string) {
    out := []string{}
    for _, k := range b.order { if k != key { out = append(out, k) } }
    b.order = append(out, key)
}
func (b *FreezeBag) Put(key string, value int) {
    if _, ok := b.vals[key]; ok {
        b.vals[key] = value
        b.touch(key)
        return
    }
    if len(b.vals) >= b.cap {
        victim := ""
        for _, k := range b.order {
            if !b.frozen[k] { victim = k; break }
        }
        if victim == "" { return }
        delete(b.vals, victim)
        out := []string{}
        for _, k := range b.order { if k != victim { out = append(out, k) } }
        b.order = out
    }
    b.vals[key] = value
    b.touch(key)
}
func (b *FreezeBag) Get(key string) (int, bool) { v, ok := b.vals[key]; return v, ok }
func (b *FreezeBag) Freeze(key string) { if _, ok := b.vals[key]; ok { b.frozen[key] = true } }
""",
    "bank/tests/go/safe_counter_test.go": """
package solution
import "sync"
type SafeCounter struct { mu sync.Mutex; n int }
func NewSafeCounter() *SafeCounter { return &SafeCounter{} }
func (c *SafeCounter) Increment() { c.mu.Lock(); c.n++; c.mu.Unlock() }
func (c *SafeCounter) Value() int { c.mu.Lock(); defer c.mu.Unlock(); return c.n }
""",
}

TS = {
    "bank/tests/ts/pack_runs.ts": """
export function packRuns(xs: number[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  if (!xs.length) return out;
  let cur = xs[0], cnt = 1;
  for (let i = 1; i < xs.length; i++) {
    if (xs[i] === cur) cnt++;
    else { out.push([cur, cnt]); cur = xs[i]; cnt = 1; }
  }
  out.push([cur, cnt]);
  return out;
}
""",
    "bank/tests/ts/validate_user.ts": """
export function validateUser(obj: Record<string, unknown>): string[] {
  const err: string[] = [];
  if (typeof obj.name !== "string" || obj.name === "") err.push("name");
  if (typeof obj.age !== "number" || !Number.isInteger(obj.age) || obj.age < 0 || obj.age > 120) err.push("age");
  return err;
}
""",
    "bank/tests/ts/parse_badge.ts": """
export function parseBadge(s: string): [number, number, number, number] | null {
  const m = /^(\\d{2})#(\\d{2})\\.(\\d{2})\\+(\\d)$/.exec(s);
  if (!m) return null;
  const y = 2000 + Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const n = Number(m[4]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
  return [y, mo, d, n];
}
""",
    "bank/tests/ts/apply_ops.ts": """
export function applyOps(ops: string[]): { A: number; B: number; C: number } {
  const bins: Record<string, number> = { A: 0, B: 0, C: 0 };
  const nxt: Record<string, string> = { A: "B", B: "C", C: "A" };
  for (const raw of ops) {
    const p = raw.split(/\\s+/);
    if (p[0] === "+") bins[p[1]] += Number(p[2]);
    else if (p[0] === "-") { const n = Number(p[2]); if (bins[p[1]] >= n) bins[p[1]] -= n; }
    else if (p[0] === ">") { bins[p[2]] += bins[p[1]]; bins[p[1]] = 0; }
    else if (p[0] === "?" && bins[p[1]] > 0) { bins[p[1]]--; bins[nxt[p[1]]]++; }
  }
  return { A: bins.A, B: bins.B, C: bins.C };
}
""",
    "bank/tests/ts/cook_text.ts": """
export function cookText(s: string): { vowels: Record<string, number>; squeezes: number; nums: number[] } {
  const vowels: Record<string, number> = {};
  const nums: number[] = [];
  let squeezes = 0;
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (c >= "0" && c <= "9") {
      let n = 0;
      while (i < s.length && s[i] >= "0" && s[i] <= "9") { n = n * 10 + Number(s[i]); i++; }
      nums.push(n);
      continue;
    }
    let run = 1;
    while (i + run < s.length && s[i + run] === c) run++;
    const low = c.toLowerCase();
    if ("aeiou".includes(low)) vowels[low] = (vowels[low] || 0) + run;
    if (/[A-Za-z]/.test(c) && run > 1) squeezes += run - 1;
    i += run;
  }
  return { vowels, squeezes, nums };
}
""",
    "bank/tests/ts/orders_sql.ts": """
export function ordersForUserSql(userId: number): string {
  return `SELECT id, user_id, created_at, amount FROM orders WHERE user_id = ${userId} ORDER BY created_at DESC LIMIT 20`;
}
""",
    "bank/tests/ts/freeze_bag.ts": """
export class FreezeBag {
  cap: number;
  order: string[] = [];
  vals = new Map<string, number>();
  frozen = new Set<string>();
  constructor(capacity: number) { this.cap = capacity; }
  touch(key: string) { this.order = this.order.filter((k) => k !== key); this.order.push(key); }
  put(key: string, value: number) {
    if (this.vals.has(key)) { this.vals.set(key, value); this.touch(key); return; }
    if (this.vals.size >= this.cap) {
      const victim = this.order.find((k) => !this.frozen.has(k));
      if (!victim) return;
      this.vals.delete(victim);
      this.order = this.order.filter((k) => k !== victim);
    }
    this.vals.set(key, value);
    this.touch(key);
  }
  get(key: string): number | null { return this.vals.has(key) ? this.vals.get(key)! : null; }
  freeze(key: string) { if (this.vals.has(key)) this.frozen.add(key); }
}
""",
    "bank/tests/ts/safe_counter.ts": """
export class SafeCounter {
  n = 0;
  increment() { this.n++; }
  value() { return this.n; }
}
""",
}


def main() -> None:
    failed = 0
    for rel, code in GO.items():
        status, detail = run_go_sandbox(code, ROOT / rel)
        print(f"GO {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    for rel, code in TS.items():
        status, detail = run_ts_sandbox(code, ROOT / rel)
        print(f"TS {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    if failed:
        raise SystemExit(failed)


if __name__ == "__main__":
    main()
