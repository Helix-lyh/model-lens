package solution

import (
	"fmt"
	"testing"
)

func eqBins(got map[string]int, want map[string]int) bool {
	if got == nil {
		return false
	}
	for _, k := range []string{"A", "B", "C"} {
		if got[k] != want[k] {
			return false
		}
	}
	return true
}

func hitOps(ops []string, want map[string]int) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	if eqBins(ApplyOps(ops), want) {
		return 1
	}
	return 0
}

func TestApplyOps(t *testing.T) {
	n := 0
	n += hitOps(nil, map[string]int{"A": 0, "B": 0, "C": 0})
	n += hitOps([]string{"+ A 3"}, map[string]int{"A": 3, "B": 0, "C": 0})
	n += hitOps([]string{"+ A 2", "- A 5"}, map[string]int{"A": 2, "B": 0, "C": 0})
	n += hitOps([]string{"+ A 4", "> A B"}, map[string]int{"A": 0, "B": 4, "C": 0})
	n += hitOps([]string{"+ C 1", "? C"}, map[string]int{"A": 1, "B": 0, "C": 0})
	n += hitOps([]string{"+ B 2", "? B", "? B"}, map[string]int{"A": 0, "B": 0, "C": 2})
	fmt.Printf("POINTS %d/6\n", n)
}
