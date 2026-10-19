// 配送复核器：按题面独立枚举，不剪枝，不引用 engine。
package oracle

import (
	"sort"
	"strconv"

	"worldkitsolve/world"
)

type Metrics struct {
	Total int
	LateN int
	Walk  int
}

func (m Metrics) Get(name string) int {
	switch name {
	case "total":
		return m.Total
	case "late_n":
		return m.LateN
	case "walk":
		return m.Walk
	default:
		return 0
	}
}

type Result struct {
	Status string
	Tops   []Metrics
	Active string
}

func Answers(w world.World) (mainSet [][]any, perQ map[string][]any) {
	r := solve(w, "")
	mains := w.MainQuestions()
	if r.Status != "ok" {
		mainSet = [][]any{{"无解"}}
	} else {
		seen := map[string][]any{}
		for _, m := range r.Tops {
			row := make([]any, len(mains))
			for i, q := range mains {
				row[i] = m.Get(q.Metric)
			}
			seen[key(row)] = row
		}
		for _, row := range seen {
			mainSet = append(mainSet, row)
		}
	}
	perQ = map[string][]any{}
	for _, q := range w.Questions {
		if q.CF != "" {
			other := "flood"
			if r.Active == "flood" {
				other = "closed"
			}
			cf := solve(w, other)
			perQ[q.Name] = metricSet(cf, q.Metric)
		} else {
			perQ[q.Name] = metricSet(r, q.Metric)
		}
	}
	return mainSet, perQ
}

func metricSet(r Result, metric string) []any {
	if r.Status != "ok" {
		return []any{"无解"}
	}
	seen := map[int]bool{}
	var out []any
	for _, m := range r.Tops {
		v := m.Get(metric)
		if !seen[v] {
			seen[v] = true
			out = append(out, v)
		}
	}
	return out
}

func key(row []any) string {
	s := ""
	for _, v := range row {
		s += "|" + anyStr(v)
	}
	return s
}

func anyStr(v any) string {
	switch x := v.(type) {
	case int:
		return strconv.Itoa(x)
	case string:
		return x
	default:
		return ""
	}
}

func solve(w world.World, force string) Result {
	mods, active := resolve(w, force)
	cancelled := map[string]bool{}
	if mods.Cancel != nil {
		for _, id := range mods.Cancel.IDs {
			cancelled[id] = true
		}
	}
	var todo []string
	for id := range w.Data.Orders {
		if !cancelled[id] {
			todo = append(todo, id)
		}
	}
	var results []Metrics
	for _, route := range routes(todo, mods.ReturnW != nil) {
		if m, ok := run(w, mods, route); ok {
			results = append(results, m)
		}
	}
	if len(results) == 0 {
		return Result{Status: "infeasible", Active: active}
	}
	best := rank(w, results[0])
	for _, m := range results[1:] {
		k := rank(w, m)
		if cmp(k, best) < 0 {
			best = k
		}
	}
	var tops []Metrics
	for _, m := range results {
		if cmp(rank(w, m), best) == 0 {
			tops = append(tops, m)
		}
	}
	return Result{Status: "ok", Tops: tops, Active: active}
}

func rank(w world.World, m Metrics) []int {
	k := make([]int, len(w.Objective))
	for i, name := range w.Objective {
		k[i] = m.Get(name)
	}
	return k
}

func cmp(a, b []int) int {
	for i := range a {
		if a[i] != b[i] {
			return a[i] - b[i]
		}
	}
	return 0
}

type cand struct {
	t, prio, idx int
	kind, bld    string
	span         [2]int
}

func resolve(w world.World, force string) (world.Modules, string) {
	mods := w.Modules
	if mods.Mutex == nil {
		return mods, ""
	}
	var cs []cand
	if mods.Flood != nil {
		cs = append(cs, cand{t: mods.Flood.T, prio: 0, kind: "flood", idx: len(cs)})
	}
	if mods.Closed != nil {
		var blds []string
		for b := range mods.Closed.Spans {
			blds = append(blds, b)
		}
		sort.Strings(blds)
		for _, b := range blds {
			for _, sp := range mods.Closed.Spans[b] {
				cs = append(cs, cand{t: sp[0], prio: 1, kind: "closed", bld: b, span: sp, idx: len(cs)})
			}
		}
	}
	if len(cs) < 2 {
		return mods, ""
	}
	if force != "" {
		var kept []cand
		for _, c := range cs {
			if c.kind == force {
				kept = append(kept, c)
			}
		}
		cs = kept
	}
	if len(cs) == 0 {
		return mods, ""
	}
	sort.SliceStable(cs, func(i, j int) bool {
		a, b := cs[i], cs[j]
		if a.t != b.t {
			return a.t < b.t
		}
		if a.prio != b.prio {
			return a.prio < b.prio
		}
		if a.bld != b.bld {
			return a.bld < b.bld
		}
		return a.idx < b.idx
	})
	top := cs[0]
	out := mods
	if top.kind == "flood" {
		out.Closed = nil
	} else {
		out.Flood = nil
		out.Closed = &world.Closed{Spans: map[string][][2]int{top.bld: {top.span}}}
	}
	return out, top.kind
}

func routes(orders []string, free bool) [][]string {
	type node struct {
		route []string
		left  map[string]bool
	}
	left0 := map[string]bool{}
	for _, id := range orders {
		left0[id] = true
	}
	var out [][]string
	stack := []node{{left: left0}}
	for len(stack) > 0 {
		cur := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		if len(cur.left) == 0 {
			out = append(out, cur.route)
			continue
		}
		var ids []string
		for id := range cur.left {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		for i := len(ids) - 1; i >= 0; i-- {
			id := ids[i]
			next := map[string]bool{}
			for k, v := range cur.left {
				if k != id {
					next[k] = v
				}
			}
			route := append(append([]string(nil), cur.route...), id)
			stack = append(stack, node{route: route, left: next})
			if free && len(cur.route) > 0 && cur.route[len(cur.route)-1] != "W" {
				withW := append(append([]string(nil), cur.route...), "W", id)
				stack = append(stack, node{route: withW, left: copySet(next)})
			}
		}
	}
	return out
}

func copySet(m map[string]bool) map[string]bool {
	n := map[string]bool{}
	for k, v := range m {
		n[k] = v
	}
	return n
}

func minutes(roads map[string]int, a, b string) int {
	if a == b {
		return 0
	}
	if v, ok := roads[a+"-"+b]; ok {
		return v
	}
	return roads[b+"-"+a]
}

func run(w world.World, mods world.Modules, route []string) (Metrics, bool) {
	orders := w.Data.Orders
	useReady := mods.Ready != nil
	t := 0
	here := "W"
	floorNow := 0
	inARow := 0
	seen := map[string]bool{}
	walk := 0
	type stop struct {
		id string
		at int
	}
	var done []stop
	descend := func(target string) {
		if floorNow > 0 && mods.Down != nil {
			t += floorNow * mods.Down.Rate
		}
		leg := minutes(w.Data.Roads, here, target)
		if mods.Congestion != nil && t >= mods.Congestion.From {
			leg *= mods.Congestion.Mult
		}
		t += leg
	}
	for _, s := range route {
		if s == "W" {
			if here != "W" {
				descend("W")
				here, floorNow, inARow = "W", 0, 0
			}
			continue
		}
		if mods.Carry != nil && inARow >= mods.Carry.Max && here != "W" {
			descend("W")
			here, floorNow, inARow = "W", 0, 0
		}
		o := orders[s]
		bld := o.Building
		descend(bld)
		arrive := t
		if mods.Flood != nil && mods.Flood.Building == bld && t >= mods.Flood.T {
			return Metrics{}, false
		}
		if mods.Register != nil && !seen[bld] {
			t += mods.Register.Minutes[bld]
		}
		seen[bld] = true
		if mods.Closed != nil {
			spans := append([][2]int(nil), mods.Closed.Spans[bld]...)
			sort.Slice(spans, func(i, j int) bool {
				if spans[i][0] != spans[j][0] {
					return spans[i][0] < spans[j][0]
				}
				return spans[i][1] < spans[j][1]
			})
			waiting := true
			for waiting {
				waiting = false
				for _, sp := range spans {
					if sp[0] <= t && t < sp[1] {
						t = sp[1]
						waiting = true
					}
				}
			}
		}
		if useReady && t < o.Ready {
			t = o.Ready
		}
		if mods.Outage != nil {
			judge := t
			if mods.Outage.CheckAt == "arrival" {
				judge = arrive
			}
			stopped := false
			for _, sp := range mods.Outage.Spans[bld] {
				if sp[0] <= judge && judge < sp[1] {
					stopped = true
				}
			}
			if stopped {
				t += 2 * o.Floor
				walk += 2 * o.Floor
			} else {
				t += o.Floor
			}
		} else {
			t += o.Floor
		}
		scope := "deliver"
		if mods.Flood != nil && mods.Flood.Scope != "" {
			scope = mods.Flood.Scope
		}
		if mods.Flood != nil && mods.Flood.Building == bld && scope == "deliver" && t >= mods.Flood.T {
			return Metrics{}, false
		}
		done = append(done, stop{s, t})
		here, floorNow, inARow = bld, o.Floor, inARow+1
	}
	if len(done) == 0 {
		return Metrics{}, false
	}
	late := 0
	for _, d := range done {
		o := orders[d.id]
		bad := d.at > o.Deadline
		if mods.Cold != nil {
			start := 0
			if useReady {
				start = o.Ready
			}
			bad = bad || d.at > start+mods.Cold.Limit
		}
		if bad {
			late++
		}
	}
	return Metrics{Total: done[len(done)-1].at, LateN: late, Walk: walk}, true
}
