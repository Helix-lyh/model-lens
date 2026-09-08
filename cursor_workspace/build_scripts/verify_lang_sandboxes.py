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
    "bank/tests/go/tag_scores_test.go": """
package solution
import (
    "strconv"
    "strings"
)
func TagScores(items []string) map[string]int {
    out := map[string]int{}
    for _, item := range items {
        idx := strings.Index(item, ":")
        if idx <= 0 { continue }
        score := item[idx+1:]
        val, ok := parseStrictInt(score)
        if !ok { continue }
        out[item[:idx]] += val
    }
    return out
}
func parseStrictInt(s string) (int, bool) {
    if s == "" { return 0, false }
    i := 0
    if s[0] == '-' {
        if len(s) == 1 { return 0, false }
        i = 1
    }
    for ; i < len(s); i++ {
        if s[i] < '0' || s[i] > '9' { return 0, false }
    }
    n, err := strconv.Atoi(s)
    return n, err == nil
}
""",
    "bank/tests/go/render_test.go": """
package solution
import "strings"
func isNameChar(c byte) bool {
    return c == '_' || (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
}
func Render(template string, vars map[string]string) string {
    var b strings.Builder
    i := 0
    for i < len(template) {
        if strings.HasPrefix(template[i:], "{{") { b.WriteByte('{'); i += 2; continue }
        if strings.HasPrefix(template[i:], "}}") { b.WriteByte('}'); i += 2; continue }
        if template[i] == '{' {
            j := i + 1
            for j < len(template) && isNameChar(template[j]) { j++ }
            if j > i+1 && j < len(template) && template[j] == '}' {
                if val, ok := vars[template[i+1:j]]; ok { b.WriteString(val) } else { b.WriteString(template[i : j+1]) }
                i = j + 1
                continue
            }
        }
        b.WriteByte(template[i])
        i++
    }
    return b.String()
}
""",
    "bank/tests/go/limiter_test.go": """
package solution
type SlidingLimiter struct {
    limit, window int
    allowed       []int
}
func NewSlidingLimiter(limit, window int) *SlidingLimiter {
    return &SlidingLimiter{limit: limit, window: window}
}
func (s *SlidingLimiter) Allow(ts int) bool {
    lo := ts - s.window
    kept := s.allowed[:0]
    for _, t := range s.allowed {
        if t > lo { kept = append(kept, t) }
    }
    s.allowed = kept
    if len(s.allowed) < s.limit {
        s.allowed = append(s.allowed, ts)
        return true
    }
    return false
}
""",
    "bank/tests/go/plan_tasks_test.go": """
package solution
import "sort"
func PlanTasks(tasks []string, deps [][2]string) ([]string, bool) {
    seen := map[[2]string]bool{}
    indeg := map[string]int{}
    after := map[string][]string{}
    for _, t := range tasks { indeg[t] = 0 }
    for _, d := range deps {
        if seen[d] { continue }
        seen[d] = true
        indeg[d[0]]++
        after[d[1]] = append(after[d[1]], d[0])
    }
    var ready []string
    for _, t := range tasks {
        if indeg[t] == 0 { ready = append(ready, t) }
    }
    sort.Strings(ready)
    var out []string
    for len(ready) > 0 {
        t := ready[0]
        ready = ready[1:]
        out = append(out, t)
        changed := false
        for _, nxt := range after[t] {
            indeg[nxt]--
            if indeg[nxt] == 0 { ready = append(ready, nxt); changed = true }
        }
        if changed { sort.Strings(ready) }
    }
    if len(out) != len(tasks) { return nil, false }
    return out, true
}
""",
    "bank/tests/go/replay_counter_test.go": """
package solution

type replayDebit struct { amount, refunded int }
func ReplayCounter(log [][3]interface{}) map[string]interface{} {
    balance := 0
    seen := map[string]bool{}
    accepted := []string{}
    rejected := []string{}
    debits := []replayDebit{}
    for _, event := range log {
        id, _ := event[0].(string)
        kind, _ := event[1].(string)
        amount, _ := event[2].(int)
        if seen[id] {
            rejected = append(rejected, id)
            continue
        }
        seen[id] = true
        switch kind {
        case "credit":
            balance += amount
            accepted = append(accepted, id)
        case "debit":
            if amount <= balance {
                balance -= amount
                debits = append(debits, replayDebit{amount: amount})
                accepted = append(accepted, id)
            } else {
                rejected = append(rejected, id)
            }
        case "refund":
            refunded := false
            for i := range debits {
                if debits[i].amount-debits[i].refunded >= amount {
                    debits[i].refunded += amount
                    balance += amount
                    accepted = append(accepted, id)
                    refunded = true
                    break
                }
            }
            if !refunded { rejected = append(rejected, id) }
        default:
            rejected = append(rejected, id)
        }
    }
    return map[string]interface{}{"balance": balance, "accepted": accepted, "rejected": rejected}
}
""",
    "bank/tests/go/merge_budget_test.go": """
package solution

import "sort"
func MergeBudget(intervals [][2]int, budget int) map[string]interface{} {
    if budget < 0 { return map[string]interface{}{"ok": false, "intervals": [][2]int{}, "reason": "invalid"} }
    work := append([][2]int{}, intervals...)
    for _, pair := range work {
        if pair[0] > pair[1] { return map[string]interface{}{"ok": false, "intervals": [][2]int{}, "reason": "invalid"} }
    }
    sort.Slice(work, func(i, j int) bool {
        if work[i][0] != work[j][0] { return work[i][0] < work[j][0] }
        return work[i][1] < work[j][1]
    })
    merged := [][2]int{}
    for _, pair := range work {
        if len(merged) > 0 && pair[0] <= merged[len(merged)-1][1]+1 {
            if pair[1] > merged[len(merged)-1][1] { merged[len(merged)-1][1] = pair[1] }
        } else { merged = append(merged, pair) }
    }
    total := 0
    for _, pair := range merged { total += pair[1]-pair[0]+1 }
    if total > budget { return map[string]interface{}{"ok": false, "intervals": [][2]int{}, "reason": "budget_exceeded"} }
    return map[string]interface{}{"ok": true, "intervals": merged, "reason": "empty"}
}
""",
    "bank/tests/go/knapsack_test.go": """
package solution

func lexLess(a, b []int) bool {
    for i := 0; i < len(a) && i < len(b); i++ {
        if a[i] != b[i] { return a[i] < b[i] }
    }
    return len(a) < len(b)
}
func betterKnapsack(value, weight int, indices []int, bestValue, bestWeight int, bestIndices []int) bool {
    if value != bestValue { return value > bestValue }
    return lexLess(indices, bestIndices)
}
func BoundedKnapsack(items [][2]int, capacity int) map[string]interface{} {
    bestValue, bestWeight := 0, 0
    bestIndices := []int{}
    if capacity < 0 { return map[string]interface{}{"value": 0, "weight": 0, "indices": bestIndices} }
    for mask := 0; mask < (1 << len(items)); mask++ {
        value, weight := 0, 0
        indices := []int{}
        for i, item := range items {
            if mask&(1<<i) != 0 { weight += item[0]; value += item[1]; indices = append(indices, i) }
        }
        if weight <= capacity && betterKnapsack(value, weight, indices, bestValue, bestWeight, bestIndices) {
            bestValue, bestWeight, bestIndices = value, weight, indices
        }
    }
    return map[string]interface{}{"value": bestValue, "weight": bestWeight, "indices": bestIndices}
}
""",
    "bank/tests/go/mvcc_test.go": """
package solution

import "sort"
func ApplyTransactions(initial map[string]int, txns []map[string]interface{}) map[string]interface{} {
    state := map[string]int{}
    versions := map[string]int{}
    for key, value := range initial { state[key] = value; versions[key] = 0 }
    statuses := map[string]string{}
    for _, txn := range txns { id, _ := txn["id"].(string); statuses[id] = "" }
    ordered := append([]map[string]interface{}{}, txns...)
    sort.SliceStable(ordered, func(i, j int) bool { return ordered[i]["commit"].(int) < ordered[j]["commit"].(int) })
    nextVersion := 0
    for _, txn := range ordered {
        id := txn["id"].(string)
        begin := txn["begin"].(int)
        writes := txn["writes"].(map[string]interface{})
        conflict := false
        for key := range writes { if versions[key] > begin { conflict = true; break } }
        if conflict { statuses[id] = "ABORT"; continue }
        nextVersion++
        statuses[id] = "COMMIT"
        for key, value := range writes { state[key] = value.(int); versions[key] = nextVersion }
    }
    return map[string]interface{}{"state": state, "statuses": statuses}
}
""",
    "bank/tests/go/order_events_test.go": """
package solution

func OrderEvents(events [][2]string) map[string]interface{} {
    state := "CREATED"
    applied, rejected := []string{}, []string{}
    seen := map[string]bool{}
    transitions := map[[2]string]string{
        {"CREATED", "PAY"}: "PAID", {"PAID", "SHIP"}: "SHIPPED",
        {"SHIPPED", "DELIVER"}: "DELIVERED", {"PAID", "REFUND"}: "REFUNDED",
        {"SHIPPED", "REFUND"}: "REFUNDED",
        {"CREATED", "CANCEL"}: "CANCELLED",
    }
    for _, event := range events {
        id, kind := event[0], event[1]
        if seen[id] { continue }
        seen[id] = true
        next, ok := transitions[[2]string{state, kind}]
        if !ok { rejected = append(rejected, id) } else { state = next; applied = append(applied, id) }
    }
    return map[string]interface{}{"state": state, "applied": applied, "rejected": rejected}
}
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
    "bank/tests/ts/tag_scores.ts": """
export function tagScores(items: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const item of items) {
    const idx = item.indexOf(":");
    if (idx <= 0) continue;
    const score = item.slice(idx + 1);
    if (!/^-?\\d+$/.test(score)) continue;
    const tag = item.slice(0, idx);
    out[tag] = (out[tag] ?? 0) + parseInt(score, 10);
  }
  return out;
}
""",
    "bank/tests/ts/render.ts": """
export function render(template: string, vars: Record<string, string>): string {
  let out = "";
  let i = 0;
  const re = /\\{([A-Za-z0-9_]+)\\}/y;
  while (i < template.length) {
    if (template.startsWith("{{", i)) { out += "{"; i += 2; continue; }
    if (template.startsWith("}}", i)) { out += "}"; i += 2; continue; }
    if (template[i] === "{") {
      re.lastIndex = i;
      const m = re.exec(template);
      if (m) {
        out += Object.prototype.hasOwnProperty.call(vars, m[1]) ? vars[m[1]] : m[0];
        i = re.lastIndex;
        continue;
      }
    }
    out += template[i];
    i++;
  }
  return out;
}
""",
    "bank/tests/ts/limiter.ts": """
export class SlidingLimiter {
  private allowed: number[] = [];
  constructor(private limit: number, private window: number) {}
  allow(ts: number): boolean {
    const lo = ts - this.window;
    this.allowed = this.allowed.filter((t) => t > lo);
    if (this.allowed.length < this.limit) {
      this.allowed.push(ts);
      return true;
    }
    return false;
  }
}
""",
    "bank/tests/ts/plan_tasks.ts": """
export function planTasks(tasks: string[], deps: Array<[string, string]>): string[] | null {
  const seen = new Set<string>();
  const indeg = new Map<string, number>();
  const after = new Map<string, string[]>();
  for (const t of tasks) indeg.set(t, 0);
  for (const [a, b] of deps) {
    const key = a + "\\u0000" + b;
    if (seen.has(key)) continue;
    seen.add(key);
    indeg.set(a, (indeg.get(a) ?? 0) + 1);
    if (!after.has(b)) after.set(b, []);
    after.get(b)!.push(a);
  }
  const ready = tasks.filter((t) => indeg.get(t) === 0).sort();
  const out: string[] = [];
  while (ready.length > 0) {
    const t = ready.shift()!;
    out.push(t);
    let changed = false;
    for (const nxt of after.get(t) ?? []) {
      indeg.set(nxt, indeg.get(nxt)! - 1);
      if (indeg.get(nxt) === 0) { ready.push(nxt); changed = true; }
    }
    if (changed) ready.sort();
  }
  return out.length === tasks.length ? out : null;
}
""",
    "bank/tests/ts/replay_counter.ts": """
type ReplayResult = { balance: number; accepted: string[]; rejected: string[] };
type Debit = { amount: number; refunded: number };
export function replayCounter(log: Array<[string, string, number]>): ReplayResult {
  let balance = 0;
  const seen = new Set<string>();
  const accepted: string[] = [];
  const rejected: string[] = [];
  const debits: Debit[] = [];
  for (const [id, kind, amount] of log) {
    if (seen.has(id)) { rejected.push(id); continue; }
    seen.add(id);
    if (kind === "credit") {
      balance += amount;
      accepted.push(id);
    } else if (kind === "debit") {
      if (amount <= balance) {
        balance -= amount;
        debits.push({ amount, refunded: 0 });
        accepted.push(id);
      } else {
        rejected.push(id);
      }
    } else if (kind === "refund") {
      const debit = debits.find((row) => row.amount - row.refunded >= amount);
      if (debit) {
        debit.refunded += amount;
        balance += amount;
        accepted.push(id);
      } else {
        rejected.push(id);
      }
    } else {
      rejected.push(id);
    }
  }
  return { balance, accepted, rejected };
}
""",
    "bank/tests/ts/merge_budget.ts": """
type MergeResult = { ok: boolean; intervals: Array<[number, number]>; reason: string };
export function mergeBudget(intervals: Array<[number, number]>, budget: number): MergeResult {
  if (!Number.isInteger(budget) || budget < 0) return { ok: false, intervals: [], reason: "invalid" };
  if (intervals.some(([left, right]) => !Number.isInteger(left) || !Number.isInteger(right) || left > right)) {
    return { ok: false, intervals: [], reason: "invalid" };
  }
  const ordered = intervals.map(([left, right]) => [left, right] as [number, number]);
  ordered.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const [left, right] of ordered) {
    const last = merged[merged.length - 1];
    if (last && left <= last[1] + 1) last[1] = Math.max(last[1], right);
    else merged.push([left, right]);
  }
  const used = merged.reduce((sum, [left, right]) => sum + right - left + 1, 0);
  if (used > budget) return { ok: false, intervals: [], reason: "budget_exceeded" };
  return { ok: true, intervals: merged, reason: "empty" };
}
""",
    "bank/tests/ts/knapsack.ts": """
type Item = [number, number];
type KnapsackResult = { value: number; weight: number; indices: number[] };
function lexLess(a: number[], b: number[]): boolean {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] < b[i];
  }
  return a.length < b.length;
}
export function boundedKnapsack(items: Item[], capacity: number): KnapsackResult {
  let best: KnapsackResult = { value: 0, weight: 0, indices: [] };
  if (!Number.isInteger(capacity) || capacity < 0) return best;
  for (let mask = 0; mask < 2 ** items.length; mask++) {
    let value = 0;
    let weight = 0;
    const indices: number[] = [];
    for (let i = 0; i < items.length; i++) {
      if (mask & 2 ** i) { weight += items[i][0]; value += items[i][1]; indices.push(i); }
    }
    if (weight > capacity) continue;
    if (value > best.value ||
        (value === best.value && lexLess(indices, best.indices))) {
      best = { value, weight, indices };
    }
  }
  return best;
}
""",
    "bank/tests/ts/mvcc.ts": """
type Transaction = { id: string; begin: number; writes: Record<string, number>; commit: number };
type MVCCResult = { state: Record<string, number>; statuses: Record<string, string> };
export function applyTransactions(initial: Record<string, number>, txns: Transaction[]): MVCCResult {
  const state = { ...initial };
  const versions: Record<string, number> = {};
  for (const key of Object.keys(state)) versions[key] = 0;
  const statuses: Record<string, string> = {};
  for (const txn of txns) statuses[txn.id] = "";
  let committedVersion = 0;
  for (const txn of [...txns].sort((a, b) => a.commit - b.commit)) {
    const conflict = Object.keys(txn.writes).some((key) => (versions[key] ?? 0) > txn.begin);
    if (conflict) { statuses[txn.id] = "ABORT"; continue; }
    committedVersion++;
    statuses[txn.id] = "COMMIT";
    for (const [key, value] of Object.entries(txn.writes)) {
      state[key] = value;
      versions[key] = committedVersion;
    }
  }
  return { state, statuses };
}
""",
    "bank/tests/ts/order_events.ts": """
type OrderResult = { state: string; applied: string[]; rejected: string[] };
export function orderEvents(events: Array<[string, string]>): OrderResult {
  let state = "CREATED";
  const applied: string[] = [];
  const rejected: string[] = [];
  const seen = new Set<string>();
  const transitions: Record<string, string> = {
    "CREATED:PAY": "PAID", "PAID:SHIP": "SHIPPED", "SHIPPED:DELIVER": "DELIVERED",
    "PAID:REFUND": "REFUNDED", "SHIPPED:REFUND": "REFUNDED",
    "CREATED:CANCEL": "CANCELLED",
  };
  for (const [id, kind] of events) {
    if (seen.has(id)) continue;
    seen.add(id);
    const next = transitions[`${state}:${kind}`];
    if (next === undefined) rejected.push(id);
    else { state = next; applied.push(id); }
  }
  return { state, applied, rejected };
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
