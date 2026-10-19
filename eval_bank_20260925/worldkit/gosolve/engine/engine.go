// 配送引擎：按 families/delivery.py 的规则枚举并模拟。复核器不得引用本包。
package engine

import (
	"fmt"
	"sort"
	"time"

	"worldkitsolve/world"
)

type Budget struct {
	MaxPlans int
	Seconds  float64
}

type Outcome struct {
	Plan     []string
	Metrics  map[string]int
	Fired    map[string]bool
	Boundary int
	Arrivals map[string]int
	Late     []string
}

type Sol struct {
	Status    string
	Best      *Outcome
	Optimal   []Outcome
	NPlans    int
	NFeasible int
}

type BudgetError struct{ N int }

func (e BudgetError) Error() string { return fmt.Sprintf("%d plans", e.N) }

func Solve(w world.World, b Budget) (Sol, error) {
	if b.MaxPlans == 0 {
		b.MaxPlans = 200_000
	}
	if b.Seconds == 0 {
		b.Seconds = 20
	}
	live := Effective(w)
	start := time.Now()
	var optimal []Outcome
	var bestKey []int
	n, feasible := 0, 0
	var berr error
	eachPlan(live, func(plan []string) bool {
		n++
		if n > b.MaxPlans || (n%512 == 0 && time.Since(start).Seconds() > b.Seconds) {
			berr = BudgetError{N: n}
			return false
		}
		out := simulate(live, plan)
		if out == nil {
			return true
		}
		feasible++
		k := objKey(w, *out)
		if bestKey == nil || cmpKey(k, bestKey) < 0 {
			bestKey = k
			optimal = []Outcome{*out}
		} else if cmpKey(k, bestKey) == 0 {
			optimal = append(optimal, *out)
		}
		return true
	})
	if berr != nil {
		return Sol{}, berr
	}
	if feasible == 0 {
		return Sol{Status: "infeasible", NPlans: n}, nil
	}
	sort.Slice(optimal, func(i, j int) bool { return planLess(optimal[i].Plan, optimal[j].Plan) })
	best := optimal[0]
	return Sol{Status: "ok", Best: &best, Optimal: optimal, NPlans: n, NFeasible: feasible}, nil
}

// Trajectory 返回最优方案的送达时刻，以及每栋楼在全部可行方案里的最早送完时刻。
func Trajectory(w world.World, b Budget) (map[string]int, map[string]int, error) {
	if b.MaxPlans == 0 {
		b.MaxPlans = 200_000
	}
	if b.Seconds == 0 {
		b.Seconds = 20
	}
	live := Effective(w)
	start := time.Now()
	var optimal []Outcome
	var bestKey []int
	minFinish := map[string]int{}
	n := 0
	var berr error
	eachPlan(live, func(plan []string) bool {
		n++
		if n > b.MaxPlans || (n%512 == 0 && time.Since(start).Seconds() > b.Seconds) {
			berr = BudgetError{N: n}
			return false
		}
		out := simulate(live, plan)
		if out == nil {
			return true
		}
		k := objKey(w, *out)
		if bestKey == nil || cmpKey(k, bestKey) < 0 {
			bestKey = k
			optimal = []Outcome{*out}
		} else if cmpKey(k, bestKey) == 0 {
			optimal = append(optimal, *out)
		}
		finish := map[string]int{}
		for id, at := range out.Arrivals {
			bld := w.Data.Orders[id].Building
			if at > finish[bld] {
				finish[bld] = at
			}
		}
		for bld, at := range finish {
			if prev, ok := minFinish[bld]; !ok || at < prev {
				minFinish[bld] = at
			}
		}
		return true
	})
	if berr != nil {
		return nil, nil, berr
	}
	if len(optimal) == 0 {
		return nil, nil, nil
	}
	sort.Slice(optimal, func(i, j int) bool { return planLess(optimal[i].Plan, optimal[j].Plan) })
	return optimal[0].Arrivals, minFinish, nil
}

func objKey(w world.World, o Outcome) []int {
	k := make([]int, len(w.Objective))
	for i, m := range w.Objective {
		k[i] = o.Metrics[m]
	}
	return k
}

func cmpKey(a, b []int) int {
	for i := range a {
		if a[i] != b[i] {
			return a[i] - b[i]
		}
	}
	return 0
}

func planLess(a, b []string) bool {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return len(a) < len(b)
}

func activeOrders(w world.World) []string {
	cancelled := map[string]bool{}
	if w.Modules.Cancel != nil {
		for _, id := range w.Modules.Cancel.IDs {
			cancelled[id] = true
		}
	}
	var ids []string
	for id := range w.Data.Orders {
		if !cancelled[id] {
			ids = append(ids, id)
		}
	}
	sort.Strings(ids)
	return ids
}

func eachPlan(w world.World, fn func([]string) bool) {
	ids := activeOrders(w)
	free := w.Modules.ReturnW != nil
	perm(ids, func(p []string) bool {
		if len(p) == 0 {
			return fn(nil)
		}
		if !free {
			cp := append([]string(nil), p...)
			return fn(cp)
		}
		gaps := 0
		if len(p) > 0 {
			gaps = len(p) - 1
		}
		for mask := 0; mask < 1<<gaps; mask++ {
			route := []string{p[0]}
			for k := 0; k < gaps; k++ {
				if mask>>k&1 == 1 {
					route = append(route, "W")
				}
				route = append(route, p[k+1])
			}
			if !fn(route) {
				return false
			}
		}
		return true
	})
}

func perm(ids []string, fn func([]string) bool) {
	a := append([]string(nil), ids...)
	var rec func(int) bool
	rec = func(n int) bool {
		if n == len(a) {
			return fn(a)
		}
		for i := n; i < len(a); i++ {
			a[n], a[i] = a[i], a[n]
			if !rec(n + 1) {
				return false
			}
			a[n], a[i] = a[i], a[n]
		}
		return true
	}
	rec(0)
}

type shock struct {
	t, prio, idx int
	kind, bld    string
	span         [2]int
}

func Effective(w world.World) world.World {
	if w.Modules.Mutex == nil {
		return w
	}
	ev := shocks(w)
	if len(ev) < 2 {
		return w
	}
	pool := ev
	if w.Modules.Mutex.Force != "" {
		pool = nil
		for _, e := range ev {
			if e.kind == w.Modules.Mutex.Force {
				pool = append(pool, e)
			}
		}
		if len(pool) == 0 {
			return w
		}
	}
	best := pool[0]
	for _, e := range pool[1:] {
		if shockLess(e, best) {
			best = e
		}
	}
	x := w.Clone()
	if best.kind == "flood" {
		x.Modules.Closed = nil
	} else {
		x.Modules.Flood = nil
		x.Modules.Closed = &world.Closed{Spans: map[string][][2]int{best.bld: {best.span}}}
	}
	x.ActiveShock = best.kind
	return x
}

func shocks(w world.World) []shock {
	var ev []shock
	if w.Modules.Flood != nil {
		ev = append(ev, shock{t: w.Modules.Flood.T, prio: 0, kind: "flood", idx: len(ev)})
	}
	if w.Modules.Closed != nil {
		var blds []string
		for b := range w.Modules.Closed.Spans {
			blds = append(blds, b)
		}
		sort.Strings(blds)
		for _, b := range blds {
			for _, sp := range w.Modules.Closed.Spans[b] {
				ev = append(ev, shock{t: sp[0], prio: 1, kind: "closed", bld: b, span: sp, idx: len(ev)})
			}
		}
	}
	return ev
}

func shockLess(a, b shock) bool {
	if a.t != b.t {
		return a.t < b.t
	}
	if a.prio != b.prio {
		return a.prio < b.prio
	}
	if a.bld != b.bld {
		return a.bld < b.bld
	}
	if a.span[0] != b.span[0] {
		return a.span[0] < b.span[0]
	}
	if a.span[1] != b.span[1] {
		return a.span[1] < b.span[1]
	}
	return a.idx < b.idx
}

func SwapShock(w world.World) world.World {
	if w.Modules.Mutex == nil {
		return w
	}
	live := Effective(w)
	other := "flood"
	if live.ActiveShock == "flood" {
		other = "closed"
	}
	x := w.Clone()
	x.Modules.Mutex.Force = other
	return x
}

func simulate(w world.World, plan []string) *Outcome {
	m := w.Modules
	pos, clock, prev, carry := "W", 0, 0, 0
	visited := map[string]bool{}
	fired := map[string]bool{}
	var arrivals [][2]int
	var names []string
	walk, boundary := 0, 0

	leave := func(dest string) {
		if m.Down != nil && prev > 0 {
			clock += prev * m.Down.Rate
			fired["down"] = true
		}
		d := world.Road(w.Data.Roads, pos, dest)
		if m.Congestion != nil && clock >= m.Congestion.From && d > 0 {
			d *= m.Congestion.Mult
			fired["congestion"] = true
		}
		clock += d
	}

	for _, step := range plan {
		if step == "W" {
			if pos != "W" {
				leave("W")
				pos, prev, carry = "W", 0, 0
				fired["return_w"] = true
			}
			continue
		}
		if m.Carry != nil && carry >= m.Carry.Max && pos != "W" {
			leave("W")
			pos, prev, carry = "W", 0, 0
			fired["carry"] = true
		}
		o := w.Data.Orders[step]
		b := o.Building
		leave(b)
		if m.Flood != nil && b == m.Flood.Building && clock >= m.Flood.T {
			return nil
		}
		ground := clock
		if m.Register != nil && !visited[b] {
			cost := m.Register.Minutes[b]
			clock += cost
			if cost > 0 {
				fired["register"] = true
			}
		}
		if m.Closed != nil {
			spans := append([][2]int(nil), m.Closed.Spans[b]...)
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
					if sp[0] <= clock && clock < sp[1] {
						if clock == sp[0] {
							boundary++
						}
						clock = sp[1]
						fired["closed"] = true
						waiting = true
					}
				}
			}
		}
		if m.Ready != nil {
			if clock == o.Ready && o.Ready > 0 {
				boundary++
			}
			if clock < o.Ready {
				clock = o.Ready
				fired["ready"] = true
			}
		}
		visited[b] = true
		up := o.Floor
		if m.Outage != nil {
			at := clock
			if m.Outage.CheckAt == "arrival" {
				at = ground
			}
			hit, stopped := false, false
			for _, sp := range m.Outage.Spans[b] {
				if at == sp[0] || at == sp[1] {
					hit = true
				}
				if sp[0] <= at && at < sp[1] {
					stopped = true
				}
			}
			if hit {
				boundary++
			}
			if stopped {
				walk += up * 2
				up *= 2
				fired["outage"] = true
			}
		}
		clock += up
		scope := "deliver"
		if m.Flood != nil && m.Flood.Scope != "" {
			scope = m.Flood.Scope
		}
		if m.Flood != nil && b == m.Flood.Building && scope == "deliver" && clock >= m.Flood.T {
			return nil
		}
		arrivals = append(arrivals, [2]int{0, clock})
		names = append(names, step)
		pos, prev, carry = b, o.Floor, carry+1
	}
	if len(arrivals) == 0 {
		return nil
	}
	late := 0
	lateIDs := []string{}
	for i, ar := range arrivals {
		o := w.Data.Orders[names[i]]
		readyBase := 0
		if m.Ready != nil {
			readyBase = o.Ready
		}
		coldLate := m.Cold != nil && ar[1] > readyBase+m.Cold.Limit
		if coldLate && ar[1] <= o.Deadline {
			fired["cold"] = true
		}
		if ar[1] > o.Deadline || coldLate {
			late++
			lateIDs = append(lateIDs, names[i])
		}
	}
	sort.Strings(lateIDs)
	if m.Flood != nil {
		for _, name := range names {
			if w.Data.Orders[name].Building == m.Flood.Building {
				fired["flood"] = true
				break
			}
		}
	}
	if m.Cancel != nil {
		fired["cancel"] = true
	}
	at := map[string]int{}
	for i, name := range names {
		at[name] = arrivals[i][1]
	}
	return &Outcome{Plan: plan, Metrics: map[string]int{"total": arrivals[len(arrivals)-1][1], "late_n": late, "walk": walk}, Fired: fired, Boundary: boundary, Arrivals: at, Late: lateIDs}
}
