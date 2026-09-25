package solution

import (
	"encoding/json"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

func encode(v any) json.RawMessage { b, _ := json.Marshal(v); return b }
func str(v any) string             { return v.(string) }
func num(v any) int                { return int(v.(float64)) }

func mergeIntervals(input json.RawMessage) json.RawMessage {
	var d struct{ Intervals [][]int }
	_ = json.Unmarshal(input, &d)
	sort.Slice(d.Intervals, func(i, j int) bool { return d.Intervals[i][0] < d.Intervals[j][0] })
	result := make([][]int, 0)
	for _, p := range d.Intervals {
		if p[0] == p[1] {
			continue
		}
		if len(result) > 0 && p[0] <= result[len(result)-1][1] {
			if p[1] > result[len(result)-1][1] {
				result[len(result)-1][1] = p[1]
			}
		} else {
			result = append(result, []int{p[0], p[1]})
		}
	}
	total := 0
	for _, p := range result {
		total += p[1] - p[0]
	}
	return encode(map[string]any{"intervals": result, "length": total})
}

func escapedSplit(input json.RawMessage) json.RawMessage {
	var d struct{ Text string }
	_ = json.Unmarshal(input, &d)
	fields := make([]string, 0)
	current := make([]byte, 0)
	for i := 0; i < len(d.Text); i++ {
		c := d.Text[i]
		if c == '\\' && i+1 < len(d.Text) {
			i++
			current = append(current, d.Text[i])
		} else if c == '|' {
			fields = append(fields, string(current))
			current = current[:0]
		} else {
			current = append(current, c)
		}
	}
	return encode(append(fields, string(current)))
}

func atomicStock(input json.RawMessage) json.RawMessage {
	var d struct {
		Initial map[string]int
		Events  []struct {
			ID    string
			Delta [][]any
		}
	}
	_ = json.Unmarshal(input, &d)
	stock := d.Initial
	if stock == nil {
		stock = map[string]int{}
	}
	seen := map[string]bool{}
	trace := make([]string, 0)
	for _, e := range d.Events {
		if seen[e.ID] {
			trace = append(trace, "DUP")
			continue
		}
		seen[e.ID] = true
		delta := map[string]int{}
		for _, p := range e.Delta {
			delta[str(p[0])] += num(p[1])
		}
		valid := true
		for k, v := range delta {
			if stock[k]+v < 0 {
				valid = false
			}
		}
		if !valid {
			trace = append(trace, "NEGATIVE")
			continue
		}
		for k, v := range delta {
			stock[k] += v
		}
		trace = append(trace, "OK")
	}
	keys := make([]string, 0)
	for k, v := range stock {
		if v != 0 {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	rows := make([][]any, 0)
	for _, k := range keys {
		rows = append(rows, []any{k, stock[k]})
	}
	return encode(map[string]any{"stock": rows, "trace": trace})
}

func dependencyOrder(input json.RawMessage) json.RawMessage {
	var d struct {
		Nodes []string
		Edges [][]string
	}
	_ = json.Unmarshal(input, &d)
	sort.Strings(d.Nodes)
	graph := map[string]map[string]bool{}
	degree := map[string]int{}
	for _, n := range d.Nodes {
		graph[n] = map[string]bool{}
		degree[n] = 0
	}
	for _, e := range d.Edges {
		if !graph[e[0]][e[1]] {
			graph[e[0]][e[1]] = true
			degree[e[1]]++
		}
	}
	ready := make([]string, 0)
	order := make([]string, 0)
	for _, n := range d.Nodes {
		if degree[n] == 0 {
			ready = append(ready, n)
		}
	}
	for len(ready) > 0 {
		sort.Strings(ready)
		u := ready[0]
		ready = ready[1:]
		order = append(order, u)
		for v := range graph[u] {
			degree[v]--
			if degree[v] == 0 {
				ready = append(ready, v)
			}
		}
	}
	if len(order) == len(d.Nodes) {
		return encode(map[string]any{"order": order, "cycle_nodes": []string{}})
	}
	cycle := make([]string, 0)
	for _, start := range d.Nodes {
		seen := map[string]bool{}
		todo := make([]string, 0)
		for v := range graph[start] {
			todo = append(todo, v)
		}
		for len(todo) > 0 {
			u := todo[len(todo)-1]
			todo = todo[:len(todo)-1]
			if seen[u] {
				continue
			}
			seen[u] = true
			for v := range graph[u] {
				if !seen[v] {
					todo = append(todo, v)
				}
			}
		}
		if seen[start] {
			cycle = append(cycle, start)
		}
	}
	return encode(map[string]any{"order": nil, "cycle_nodes": cycle})
}

type scheduleResult struct {
	Value int      `json:"value"`
	IDs   []string `json:"ids"`
}

func betterSchedule(a, b scheduleResult) bool {
	if a.Value != b.Value {
		return a.Value > b.Value
	}
	if len(a.IDs) != len(b.IDs) {
		return len(a.IDs) < len(b.IDs)
	}
	for i := range a.IDs {
		if a.IDs[i] != b.IDs[i] {
			return a.IDs[i] < b.IDs[i]
		}
	}
	return false
}
func weightedSchedule(input json.RawMessage) json.RawMessage {
	var d struct {
		Jobs []struct {
			ID                string
			Start, End, Value int
		}
	}
	_ = json.Unmarshal(input, &d)
	sort.Slice(d.Jobs, func(i, j int) bool {
		a, b := d.Jobs[i], d.Jobs[j]
		if a.End != b.End {
			return a.End < b.End
		}
		if a.Start != b.Start {
			return a.Start < b.Start
		}
		return a.ID < b.ID
	})
	best := []scheduleResult{{0, []string{}}}
	for i, j := range d.Jobs {
		p := sort.Search(i, func(k int) bool { return d.Jobs[k].End > j.Start })
		ids := append([]string{}, best[p].IDs...)
		ids = append(ids, j.ID)
		take := scheduleResult{best[p].Value + j.Value, ids}
		if betterSchedule(take, best[i]) {
			best = append(best, take)
		} else {
			best = append(best, best[i])
		}
	}
	return encode(best[len(best)-1])
}

type txState struct {
	Version          int
	Snapshot, Writes map[string]int
}

func snapshotTransactions(input json.RawMessage) json.RawMessage {
	var d struct {
		Initial map[string]int
		Events  [][]any
	}
	_ = json.Unmarshal(input, &d)
	current := d.Initial
	if current == nil {
		current = map[string]int{}
	}
	last := map[string]int{}
	version := 0
	active := map[string]*txState{}
	reads := make([][]any, 0)
	commits := make([][]any, 0)
	for _, e := range d.Events {
		op, tx := str(e[0]), str(e[1])
		if op == "BEGIN" {
			snapshot := map[string]int{}
			for k, v := range current {
				snapshot[k] = v
			}
			active[tx] = &txState{version, snapshot, map[string]int{}}
			continue
		}
		state := active[tx]
		if op == "GET" {
			key := str(e[2])
			var v any
			if x, ok := state.Writes[key]; ok {
				v = x
			} else if x, ok := state.Snapshot[key]; ok {
				v = x
			}
			reads = append(reads, []any{tx, key, v})
		} else if op == "SET" {
			state.Writes[str(e[2])] = num(e[3])
		} else {
			delete(active, tx)
			conflict := false
			for k := range state.Writes {
				if last[k] > state.Version {
					conflict = true
				}
			}
			if conflict {
				commits = append(commits, []any{tx, false, nil})
			} else {
				version++
				for k, v := range state.Writes {
					current[k] = v
					last[k] = version
				}
				commits = append(commits, []any{tx, true, version})
			}
		}
	}
	keys := make([]string, 0)
	for k := range current {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	final := make([][]any, 0)
	for _, k := range keys {
		final = append(final, []any{k, current[k]})
	}
	return encode(map[string]any{"reads": reads, "commits": commits, "final": final})
}

func dynamicConnectivity(input json.RawMessage) json.RawMessage {
	var d struct {
		N      int
		Events [][]any
	}
	_ = json.Unmarshal(input, &d)
	total := len(d.Events)
	if total == 0 {
		return encode([]bool{})
	}
	counts := map[[2]int]int{}
	starts := map[[2]int]int{}
	intervals := make([][4]int, 0)
	for t, e := range d.Events {
		op, u, v := str(e[0]), num(e[1]), num(e[2])
		if u > v {
			u, v = v, u
		}
		key := [2]int{u, v}
		if op == "ADD" {
			if counts[key] == 0 {
				starts[key] = t
			}
			counts[key]++
		} else if op == "REMOVE" && counts[key] > 0 {
			counts[key]--
			if counts[key] == 0 {
				intervals = append(intervals, [4]int{starts[key], t, u, v})
				delete(starts, key)
			}
		}
	}
	for e, t := range starts {
		intervals = append(intervals, [4]int{t, total, e[0], e[1]})
	}
	tree := make([][][2]int, 4*total)
	var put func(int, int, int, int, int, [2]int)
	put = func(node, l, r, a, b int, e [2]int) {
		if a >= r || b <= l {
			return
		}
		if a <= l && r <= b {
			tree[node] = append(tree[node], e)
			return
		}
		m := (l + r) / 2
		put(node*2, l, m, a, b, e)
		put(node*2+1, m, r, a, b, e)
	}
	for _, x := range intervals {
		put(1, 0, total, x[0], x[1], [2]int{x[2], x[3]})
	}
	parent, size := make([]int, d.N), make([]int, d.N)
	for i := range parent {
		parent[i] = i
		size[i] = 1
	}
	find := func(x int) int {
		for parent[x] != x {
			x = parent[x]
		}
		return x
	}
	history := make([][3]int, 0)
	answer := make([]bool, 0)
	var visit func(int, int, int)
	visit = func(node, l, r int) {
		checkpoint := len(history)
		for _, e := range tree[node] {
			a, b := find(e[0]), find(e[1])
			if a == b {
				continue
			}
			if size[a] < size[b] {
				a, b = b, a
			}
			history = append(history, [3]int{b, a, size[a]})
			parent[b] = a
			size[a] += size[b]
		}
		if r-l == 1 {
			e := d.Events[l]
			if str(e[0]) == "ASK" {
				answer = append(answer, find(num(e[1])) == find(num(e[2])))
			}
		} else {
			m := (l + r) / 2
			visit(node*2, l, m)
			visit(node*2+1, m, r)
		}
		for len(history) > checkpoint {
			x := history[len(history)-1]
			history = history[:len(history)-1]
			parent[x[0]] = x[0]
			size[x[1]] = x[2]
		}
	}
	visit(1, 0, total)
	return encode(answer)
}

func registerMachine(input json.RawMessage) json.RawMessage {
	var d struct {
		Src   string
		Limit int
	}
	_ = json.Unmarshal(input, &d)
	low, high := int64(-2147483648), int64(2147483647)
	integer := regexp.MustCompile(`^[+-]?[0-9]+$`)
	ident := regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	reg := func(s string) bool { return s == "A" || s == "B" || s == "C" }
	operand := func(s string) bool {
		if reg(s) {
			return true
		}
		if !integer.MatchString(s) {
			return false
		}
		v, e := strconv.ParseInt(s, 10, 64)
		return e == nil && v >= low && v <= high
	}
	labels := map[string]int{}
	program := make([][]string, 0)
	arity := map[string]int{"SET": 3, "ADD": 3, "MUL": 3, "MOD": 3, "JZ": 3, "JNZ": 3, "JMP": 2, "HALT": 1}
	fail := func(status string, steps int) json.RawMessage {
		return encode(map[string]any{"status": status, "steps": steps})
	}
	for _, line := range strings.Split(d.Src, "\n") {
		p := strings.Fields(strings.SplitN(line, "#", 2)[0])
		if len(p) == 0 {
			continue
		}
		op := p[0]
		if op == "LABEL" {
			if len(p) != 2 || !ident.MatchString(p[1]) {
				return fail("ERR", 0)
			}
			if _, ok := labels[p[1]]; ok {
				return fail("ERR", 0)
			}
			labels[p[1]] = len(program)
			continue
		}
		if arity[op] != len(p) {
			return fail("ERR", 0)
		}
		if (op == "SET" || op == "ADD" || op == "MUL" || op == "MOD") && (!reg(p[1]) || !operand(p[2])) {
			return fail("ERR", 0)
		}
		if (op == "JZ" || op == "JNZ") && !reg(p[1]) {
			return fail("ERR", 0)
		}
		program = append(program, p)
	}
	for _, p := range program {
		if p[0] == "JMP" || p[0] == "JZ" || p[0] == "JNZ" {
			if _, ok := labels[p[len(p)-1]]; !ok {
				return fail("ERR", 0)
			}
		}
	}
	regs := map[string]int64{"A": 0, "B": 0, "C": 0}
	pc, steps := 0, 0
	for pc < len(program) {
		if steps == d.Limit {
			return fail("TIMEOUT", steps)
		}
		p := program[pc]
		op := p[0]
		steps++
		if op == "HALT" {
			break
		}
		if op == "JMP" || op == "JZ" || op == "JNZ" {
			jump := op == "JMP" || op == "JZ" && regs[p[1]] == 0 || op == "JNZ" && regs[p[1]] != 0
			if jump {
				pc = labels[p[len(p)-1]]
			} else {
				pc++
			}
			continue
		}
		x, y := p[1], p[2]
		v, ok := regs[y]
		if !ok {
			v, _ = strconv.ParseInt(y, 10, 64)
		}
		var result int64
		switch op {
		case "SET":
			result = v
		case "ADD":
			result = regs[x] + v
		case "MUL":
			result = regs[x] * v
		case "MOD":
			if v == 0 {
				return fail("DIV0", steps)
			}
			result = regs[x] % v
			if result != 0 && (result < 0) != (v < 0) {
				result += v
			}
		}
		if result < low || result > high {
			return fail("OVERFLOW", steps)
		}
		regs[x] = result
		pc++
	}
	return encode(map[string]any{"status": "OK", "value": regs["A"], "steps": steps})
}
