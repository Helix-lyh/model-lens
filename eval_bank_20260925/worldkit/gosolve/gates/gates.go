// 门禁。消融变体并行求解；复核器对拍放在最后。
package gates

import (
	"encoding/json"
	"runtime"
	"sort"
	"sync"

	"worldkitsolve/engine"
	"worldkitsolve/oracle"
	"worldkitsolve/world"
)

type Request struct {
	ID       int         `json:"id"`
	Op       string      `json:"op"`
	World    world.World `json:"world"`
	FailFast bool        `json:"fail_fast"`
	MaxPlans int         `json:"max_plans"`
	Seconds  float64     `json:"seconds"`
}

type Solver struct {
	budget engine.Budget
	mu     sync.Mutex
	cache  map[string]engine.Sol
	err    error
}

func newSolver(maxPlans int, seconds float64) *Solver {
	return &Solver{budget: engine.Budget{MaxPlans: maxPlans, Seconds: seconds}, cache: map[string]engine.Sol{}}
}

func (s *Solver) Err() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.err
}

func (s *Solver) Solve(w world.World) engine.Sol {
	key, _ := json.Marshal(w)
	s.mu.Lock()
	if s.err != nil {
		s.mu.Unlock()
		return engine.Sol{}
	}
	if hit, ok := s.cache[string(key)]; ok {
		s.mu.Unlock()
		return hit
	}
	s.mu.Unlock()
	sol, err := engine.Solve(w, s.budget)
	s.mu.Lock()
	defer s.mu.Unlock()
	if err != nil {
		if s.err == nil {
			s.err = err
		}
		return engine.Sol{}
	}
	if prev, ok := s.cache[string(key)]; ok {
		return prev
	}
	s.cache[string(key)] = sol
	return sol
}

func (s *Solver) SolveMany(ws []world.World) []engine.Sol {
	out := make([]engine.Sol, len(ws))
	if len(ws) == 0 {
		return out
	}
	n := runtime.GOMAXPROCS(0)
	if n > len(ws) {
		n = len(ws)
	}
	sem := make(chan struct{}, n)
	var wg sync.WaitGroup
	for i := range ws {
		wg.Add(1)
		sem <- struct{}{}
		go func(i int) {
			defer wg.Done()
			defer func() { <-sem }()
			out[i] = s.Solve(ws[i])
		}(i)
	}
	wg.Wait()
	return out
}

type cond struct {
	name     string
	relaxing bool
	apply    func(world.World) world.World
}

func Trajectory(req Request) (map[string]any, error) {
	at, finish, err := engine.Trajectory(req.World, engine.Budget{MaxPlans: req.MaxPlans, Seconds: req.Seconds})
	if err != nil {
		return map[string]any{"error": "rejected:budget (" + err.Error() + ")"}, nil
	}
	if at == nil {
		return map[string]any{"status": "infeasible"}, nil
	}
	return map[string]any{"status": "ok", "arrivals": at, "min_finish": finish}, nil
}

func Status(req Request) (map[string]any, error) {
	sol, err := engine.Solve(req.World, engine.Budget{MaxPlans: req.MaxPlans, Seconds: req.Seconds})
	if err != nil {
		return map[string]any{"error": "rejected:budget (" + err.Error() + ")"}, nil
	}
	rep := map[string]any{"status": sol.Status, "plans": sol.NPlans, "feasible": sol.NFeasible}
	if sol.Best == nil {
		return rep, nil
	}
	fired := []string{}
	for id, on := range sol.Best.Fired {
		if on {
			fired = append(fired, id)
		}
	}
	sort.Strings(fired)
	late := sol.Best.Late
	if late == nil {
		late = []string{}
	}
	rep["plan"] = sol.Best.Plan
	rep["late"] = late
	rep["fired"] = fired
	rep["total"] = sol.Best.Metrics["total"]
	rep["late_n"] = sol.Best.Metrics["late_n"]
	rep["arrivals"] = sol.Best.Arrivals
	return rep, nil
}

func Run(req Request) (map[string]any, error) {
	s := newSolver(req.MaxPlans, req.Seconds)
	rep := map[string]any{"reasons": []string{}, "checks": map[string]bool{}}
	reasons := []string{}
	checks := map[string]bool{}
	add := func(name string, ok bool) bool {
		checks[name] = ok
		if !ok {
			reasons = append(reasons, name)
		}
		return ok || !req.FailFast
	}
	w := req.World
	base := s.Solve(w)
	if err := s.Err(); err != nil {
		reasons = append(reasons, "rejected:budget ("+err.Error()+")")
		rep["reasons"] = reasons
		rep["checks"] = checks
		rep["accept"] = false
		return rep, nil
	}
	conds := conditions(w)
	key := answers(s, w)
	if err := s.Err(); err != nil {
		reasons = append(reasons, "rejected:budget ("+err.Error()+")")
		rep["reasons"] = reasons
		rep["checks"] = checks
		rep["accept"] = false
		return rep, nil
	}
	rep["answer"] = key
	rep["search"] = map[string]int{"plans": base.NPlans, "feasible": base.NFeasible, "optimal": len(base.Optimal)}
	passed := true
	if base.Status == "ok" {
		rep["boundary"] = base.Best.Boundary
		rep["cf"] = cfReport(w, key)
		rep["uniqueness"] = uniqueness(s, w)
		steps := []struct {
			name string
			ok   func() bool
		}{
			{"boundary", func() bool { return base.Best.Boundary >= minBoundary(w) }},
			{"cf", func() bool { return allBool(rep["cf"].(map[string]bool)) }},
			{"uniqueness", func() bool { return allBool(rep["uniqueness"].(map[string]bool)) }},
			{"deletion", func() bool {
				rep["deletion"] = deletion(s, w, conds)
				return allDeletion(rep["deletion"].([]map[string]any))
			}},
			{"degree", func() bool {
				rep["degree"] = degree(s, w, conds, minDegree(w))
				return rep["degree"].(map[string]any)["ok"].(bool)
			}},
		}
		for _, st := range steps {
			if !add(st.name, st.ok()) {
				passed = false
				break
			}
		}
	} else {
		ok := func() bool {
			rep["conflict"] = conflict(s, w, conds)
			return rep["conflict"].(map[string]any)["ok"].(bool)
		}()
		if !add("conflict", ok) {
			passed = false
		}
	}
	if err := s.Err(); err != nil {
		reasons = append(reasons, "rejected:budget ("+err.Error()+")")
		rep["reasons"] = reasons
		rep["checks"] = checks
		rep["accept"] = false
		return rep, nil
	}
	if passed {
		orep := oracleReport(s, w, conds, key)
		rep["oracle"] = orep
		if !add("oracle", orep["ok"].(bool)) {
			passed = false
		}
		rep["readings"] = readings(s, w)
		if base.Status == "ok" {
			rep["fired"] = fired(w, base)
		}
	}
	rep["checks"] = checks
	rep["reasons"] = reasons
	rep["accept"] = len(reasons) == 0
	return rep, nil
}

func minDegree(w world.World) int {
	if w.Gates.MinDegree != nil {
		return *w.Gates.MinDegree
	}
	return 3
}

func minBoundary(w world.World) int {
	if w.Gates.MinBoundary != nil {
		return *w.Gates.MinBoundary
	}
	return 0
}

func allBool(m map[string]bool) bool {
	for _, v := range m {
		if !v {
			return false
		}
	}
	return true
}

func metric(sol engine.Sol, name string) any {
	if sol.Status != "ok" {
		return "无解"
	}
	return sol.Best.Metrics[name]
}

func answers(s *Solver, w world.World) map[string]any {
	base := s.Solve(w)
	out := map[string]any{}
	for _, q := range w.Questions {
		if q.CF != "" {
			out[q.Name] = metric(s.Solve(engine.SwapShock(w)), q.Metric)
		} else {
			out[q.Name] = metric(base, q.Metric)
		}
	}
	return out
}

func mainValues(w world.World, sol engine.Sol) []any {
	qs := w.MainQuestions()
	out := make([]any, len(qs))
	for i, q := range qs {
		out[i] = metric(sol, q.Metric)
	}
	return out
}

func same(a, b []any) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func cfReport(w world.World, key map[string]any) map[string]bool {
	mains := map[string]string{}
	for _, q := range w.MainQuestions() {
		mains[q.Metric] = q.Name
	}
	out := map[string]bool{}
	for _, q := range w.Questions {
		if q.CF != "" {
			if main, ok := mains[q.Metric]; ok {
				out[q.Name] = key[q.Name] != key[main]
			}
		}
	}
	return out
}

func optTuples(w world.World, sol engine.Sol) [][]any {
	if sol.Status != "ok" {
		return [][]any{{"无解"}}
	}
	qs := w.MainQuestions()
	var rows [][]any
	seen := map[string]bool{}
	for _, o := range sol.Optimal {
		row := make([]any, len(qs))
		id := ""
		for i, q := range qs {
			row[i] = o.Metrics[q.Metric]
			id += "|" + sprint(row[i])
		}
		if !seen[id] {
			seen[id] = true
			rows = append(rows, row)
		}
	}
	return rows
}

func sprint(v any) string {
	switch x := v.(type) {
	case int:
		return itoa(x)
	case string:
		return x
	default:
		return ""
	}
}

func uniqueness(s *Solver, w world.World) map[string]bool {
	out := map[string]bool{"main": len(optTuples(w, s.Solve(w))) == 1}
	for _, q := range w.Questions {
		if q.CF == "" {
			continue
		}
		sol := s.Solve(engine.SwapShock(w))
		if sol.Status != "ok" {
			out[q.Name] = true
			continue
		}
		seen := map[int]bool{}
		for _, o := range sol.Optimal {
			seen[o.Metrics[q.Metric]] = true
		}
		out[q.Name] = len(seen) == 1
	}
	return out
}

func deletion(s *Solver, w world.World, conds []cond) []map[string]any {
	alts := make([]world.World, len(conds))
	for i, c := range conds {
		alts[i] = c.apply(w)
	}
	sols := s.SolveMany(alts)
	base := mainValues(w, s.Solve(w))
	names := []string{}
	for _, q := range w.MainQuestions() {
		names = append(names, q.Name)
	}
	var out []map[string]any
	for i, c := range conds {
		other := mainValues(w, sols[i])
		var changed []string
		for k, name := range names {
			if base[k] != other[k] {
				changed = append(changed, name)
			}
		}
		if changed == nil {
			changed = []string{}
		}
		out = append(out, map[string]any{"condition": c.name, "changed": changed, "ok": len(changed) > 0})
	}
	return out
}

func allDeletion(rows []map[string]any) bool {
	for _, r := range rows {
		if !r["ok"].(bool) {
			return false
		}
	}
	return true
}

func degree(s *Solver, w world.World, conds []cond, min int) map[string]any {
	alts := make([]world.World, len(conds))
	for i, c := range conds {
		alts[i] = c.apply(w)
	}
	sols := s.SolveMany(alts)
	base := mainValues(w, s.Solve(w))
	single := map[string][]any{}
	for i, c := range conds {
		single[c.name] = mainValues(w, sols[i])
	}
	type pair struct{ a, b int }
	var pairs []pair
	var worlds []world.World
	for i := range conds {
		for j := range conds {
			if i == j {
				continue
			}
			pairs = append(pairs, pair{i, j})
			worlds = append(worlds, conds[i].apply(conds[j].apply(w)))
		}
	}
	psols := s.SolveMany(worlds)
	neighbors := map[string][]string{}
	for _, c := range conds {
		neighbors[c.name] = []string{}
	}
	for k, p := range pairs {
		ab := mainValues(w, psols[k])
		a, b := conds[p.a], conds[p.b]
		if interacts(base, single[a.name], single[b.name], ab) {
			neighbors[a.name] = append(neighbors[a.name], b.name)
		}
	}
	deg := map[string]int{}
	ok := len(conds) > 0
	for name, ns := range neighbors {
		deg[name] = len(ns)
		if len(ns) < min {
			ok = false
		}
	}
	return map[string]any{"neighbors": neighbors, "degree": deg, "ok": ok}
}

func interacts(base, a, b, ab []any) bool {
	return !same(a, base) && !same(b, base) && !same(ab, a) && !same(ab, b)
}

func conflict(s *Solver, w world.World, conds []cond) map[string]any {
	alts := make([]world.World, len(conds))
	for i, c := range conds {
		alts[i] = c.apply(w)
	}
	sols := s.SolveMany(alts)
	var core []string
	inCore := map[string]bool{}
	for i, c := range conds {
		if sols[i].Status == "ok" {
			core = append(core, c.name)
			inCore[c.name] = true
		}
	}
	if core == nil {
		core = []string{}
	}
	x := w
	for _, c := range conds {
		if !inCore[c.name] && c.relaxing {
			x = c.apply(x)
		}
	}
	still := s.Solve(x).Status == "infeasible"
	return map[string]any{"core": core, "unique_minimal": still && len(core) >= 1, "ok": still && len(core) >= 2}
}

func oracleReport(s *Solver, w world.World, conds []cond, key map[string]any) map[string]any {
	type item struct {
		name string
		w    world.World
	}
	vars := []item{{"base", w}}
	for _, c := range conds {
		vars = append(vars, item{c.name, c.apply(w)})
	}
	for i := range conds {
		for j := i + 1; j < len(conds); j++ {
			vars = append(vars, item{conds[i].name + "+" + conds[j].name, conds[i].apply(conds[j].apply(w))})
		}
	}
	eng := make([]map[string]bool, len(vars))
	ora := make([]map[string]bool, len(vars))
	perQ := make([]map[string][]any, len(vars))
	n := runtime.GOMAXPROCS(0)
	sem := make(chan struct{}, n)
	var wg sync.WaitGroup
	for i := range vars {
		wg.Add(1)
		sem <- struct{}{}
		go func(i int) {
			defer wg.Done()
			defer func() { <-sem }()
			sol := s.Solve(vars[i].w)
			eng[i] = tupleSet(optTuples(vars[i].w, sol))
			ms, pq := oracle.Answers(vars[i].w)
			ora[i] = tupleSet(ms)
			perQ[i] = pq
		}(i)
	}
	wg.Wait()
	var mismatches []map[string]any
	for i := range vars {
		if !setEq(eng[i], ora[i]) {
			mismatches = append(mismatches, map[string]any{"variant": vars[i].name, "engine": keys(eng[i]), "oracle": keys(ora[i])})
		}
	}
	for name, vals := range perQ[0] {
		want := map[string]bool{sprint(key[name]): true}
		got := map[string]bool{}
		for _, v := range vals {
			got[sprint(v)] = true
		}
		if !setEq(want, got) {
			mismatches = append(mismatches, map[string]any{"variant": "base", "question": name, "engine": key[name], "oracle": vals})
		}
	}
	if mismatches == nil {
		mismatches = []map[string]any{}
	}
	return map[string]any{"ok": len(mismatches) == 0, "variants": len(vars), "mismatches": mismatches}
}

func tupleSet(rows [][]any) map[string]bool {
	m := map[string]bool{}
	for _, row := range rows {
		id := ""
		for _, v := range row {
			id += "|" + sprint(v)
		}
		m[id] = true
	}
	return m
}

func setEq(a, b map[string]bool) bool {
	if len(a) != len(b) {
		return false
	}
	for k := range a {
		if !b[k] {
			return false
		}
	}
	return true
}

func keys(m map[string]bool) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func readings(s *Solver, w world.World) map[string]bool {
	base := mainValues(w, s.Solve(w))
	out := map[string]bool{}
	if alt, ok := flip(w, "flood"); ok {
		out["洪涝：送达前 / 到达前"] = !same(base, mainValues(alt, s.Solve(alt)))
	}
	if alt, ok := flip(w, "outage"); ok {
		out["停运判定：开始上楼时 / 到达地面时"] = !same(base, mainValues(alt, s.Solve(alt)))
	}
	return out
}

func flip(w world.World, which string) (world.World, bool) {
	x := w.Clone()
	switch which {
	case "flood":
		if x.Modules.Flood == nil {
			return w, false
		}
		if x.Modules.Flood.Scope == "" || x.Modules.Flood.Scope == "deliver" {
			x.Modules.Flood.Scope = "enter"
		} else {
			x.Modules.Flood.Scope = "deliver"
		}
	case "outage":
		if x.Modules.Outage == nil {
			return w, false
		}
		if x.Modules.Outage.CheckAt == "" || x.Modules.Outage.CheckAt == "climb_start" {
			x.Modules.Outage.CheckAt = "arrival"
		} else {
			x.Modules.Outage.CheckAt = "climb_start"
		}
	}
	return x, true
}

func fired(w world.World, base engine.Sol) map[string]any {
	bg := map[string]bool{}
	for _, id := range w.Background {
		bg[id] = true
	}
	effects := []struct{ id, title string }{
		{"outage", "电梯停运"}, {"register", "首次登记"}, {"closed", "楼宇封闭"},
		{"ready", "出餐时刻"}, {"down", "下楼耗时"}, {"congestion", "道路拥堵"},
		{"carry", "连续配送上限"}, {"cold", "冷链时限"},
	}
	present := map[string]bool{
		"outage": w.Modules.Outage != nil, "register": w.Modules.Register != nil,
		"closed": w.Modules.Closed != nil, "ready": w.Modules.Ready != nil,
		"down": w.Modules.Down != nil, "congestion": w.Modules.Congestion != nil,
		"carry": w.Modules.Carry != nil, "cold": w.Modules.Cold != nil,
	}
	var missing []string
	for _, e := range effects {
		if present[e.id] && !bg[e.id] && !base.Best.Fired[e.id] {
			missing = append(missing, e.title)
		}
	}
	if missing == nil {
		missing = []string{}
	}
	return map[string]any{"ok": len(missing) == 0, "missing": missing}
}

type moduleInfo struct {
	id, title string
	stage     int
	relaxing  bool
	present   func(world.Modules) bool
	drop      func(world.World) world.World
}

func catalog() []moduleInfo {
	drop := func(id string, clear func(*world.Modules)) func(world.World) world.World {
		return func(w world.World) world.World {
			x := w.Clone()
			clear(&x.Modules)
			return x
		}
	}
	return []moduleInfo{
		{"outage", "电梯停运", 10, true, func(m world.Modules) bool { return m.Outage != nil }, drop("outage", func(m *world.Modules) { m.Outage = nil })},
		{"register", "首次登记", 20, true, func(m world.Modules) bool { return m.Register != nil }, drop("register", func(m *world.Modules) { m.Register = nil })},
		{"closed", "楼宇封闭", 25, true, func(m world.Modules) bool { return m.Closed != nil }, drop("closed", func(m *world.Modules) { m.Closed = nil })},
		{"ready", "出餐时刻", 27, true, func(m world.Modules) bool { return m.Ready != nil }, drop("ready", func(m *world.Modules) { m.Ready = nil })},
		{"down", "下楼耗时", 30, true, func(m world.Modules) bool { return m.Down != nil }, drop("down", func(m *world.Modules) { m.Down = nil })},
		{"congestion", "道路拥堵", 35, true, func(m world.Modules) bool { return m.Congestion != nil }, drop("congestion", func(m *world.Modules) { m.Congestion = nil })},
		{"carry", "连续配送上限", 40, true, func(m world.Modules) bool { return m.Carry != nil }, drop("carry", func(m *world.Modules) { m.Carry = nil })},
		{"return_w", "随时回站", 41, false, func(m world.Modules) bool { return m.ReturnW != nil }, drop("return_w", func(m *world.Modules) { m.ReturnW = nil })},
		{"cancel", "订单取消", 50, false, func(m world.Modules) bool { return m.Cancel != nil }, drop("cancel", func(m *world.Modules) { m.Cancel = nil })},
		{"flood", "洪涝封楼", 55, true, func(m world.Modules) bool { return m.Flood != nil }, drop("flood", func(m *world.Modules) { m.Flood = nil })},
		{"cold", "冷链时限", 60, true, func(m world.Modules) bool { return m.Cold != nil }, drop("cold", func(m *world.Modules) { m.Cold = nil })},
		{"mutex", "洪涝封闭互斥", 70, false, func(m world.Modules) bool { return m.Mutex != nil }, drop("mutex", func(m *world.Modules) { m.Mutex = nil })},
	}
}

func conditions(w world.World) []cond {
	bg := map[string]bool{}
	for _, id := range w.Background {
		bg[id] = true
	}
	var out []cond
	for _, m := range catalog() {
		if m.present(w.Modules) && !bg[m.id] {
			out = append(out, cond{name: m.title, relaxing: m.relaxing, apply: m.drop})
		}
	}
	var layers []string
	for layer := range w.ObjectiveConditions {
		layers = append(layers, layer)
	}
	sort.Strings(layers)
	for _, layer := range layers {
		name := w.ObjectiveConditions[layer]
		layer := layer
		out = append(out, cond{name: name, relaxing: true, apply: func(w world.World) world.World {
			x := w.Clone()
			obj := []string{}
			for _, m := range x.Objective {
				if m != layer {
					obj = append(obj, m)
				}
			}
			x.Objective = obj
			delete(x.ObjectiveConditions, layer)
			return x
		}})
	}
	return out
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [16]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
