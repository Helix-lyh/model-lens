package solution

import (
	"fmt"
	"testing"
)

func eqPairs(got, want [][2]int) bool {
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

func hitPack(xs []int, want [][2]int) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	if eqPairs(PackRuns(xs), want) {
		return 1
	}
	return 0
}

func TestPackRuns(t *testing.T) {
	n := 0
	n += hitPack([]int{}, nil)
	n += hitPack([]int{7}, [][2]int{{7, 1}})
	n += hitPack([]int{1, 1, 1, 2, 2}, [][2]int{{1, 3}, {2, 2}})
	n += hitPack([]int{3, 1, 1, 3}, [][2]int{{3, 1}, {1, 2}, {3, 1}})
	n += hitPack([]int{0, 0, 0, 0}, [][2]int{{0, 4}})
	fmt.Printf("POINTS %d/5\n", n)
}
