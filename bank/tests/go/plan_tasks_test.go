package solution

import (
	"fmt"
	"testing"
)

func eqStrSlice(got, want []string) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if got[i] != want[i] {
			return false
		}
	}
	return true
}

func hitPlan(tasks []string, deps [][2]string, want []string, wantOK bool) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	got, ok := PlanTasks(tasks, deps)
	if ok != wantOK {
		return 0
	}
	if !wantOK {
		return 1
	}
	if eqStrSlice(got, want) {
		return 1
	}
	return 0
}

func TestPlanTasks(t *testing.T) {
	n := 0
	n += hitPlan([]string{"c", "a", "b"}, nil, []string{"a", "b", "c"}, true)
	n += hitPlan([]string{"a", "b", "c"}, [][2]string{{"a", "b"}, {"b", "c"}}, []string{"c", "b", "a"}, true)
	n += hitPlan([]string{"d", "b", "c", "a"}, [][2]string{{"b", "a"}, {"c", "a"}, {"d", "b"}, {"d", "c"}}, []string{"a", "b", "c", "d"}, true)
	n += hitPlan([]string{"a", "b"}, [][2]string{{"a", "b"}, {"b", "a"}}, nil, false)
	n += hitPlan([]string{"a", "b"}, [][2]string{{"b", "a"}, {"b", "a"}}, []string{"a", "b"}, true)
	n += hitPlan([]string{"t3", "t1", "x", "t2"}, [][2]string{{"t2", "t1"}, {"t3", "t2"}, {"x", "t1"}}, []string{"t1", "t2", "t3", "x"}, true)
	fmt.Printf("POINTS %d/6\n", n)
}
