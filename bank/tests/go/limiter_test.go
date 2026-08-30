package solution

import (
	"fmt"
	"testing"
)

func hitLimiter(limit, window int, seq []int, want []bool) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	lim := NewSlidingLimiter(limit, window)
	for i, ts := range seq {
		if lim.Allow(ts) != want[i] {
			return 0
		}
	}
	return 1
}

func TestSlidingLimiter(t *testing.T) {
	n := 0
	n += hitLimiter(2, 10, []int{1, 2, 3}, []bool{true, true, false})
	n += hitLimiter(2, 10, []int{1, 2, 11, 12, 12}, []bool{true, true, true, true, false})
	n += hitLimiter(1, 5, []int{0, 4, 5}, []bool{true, false, true})
	n += hitLimiter(1, 3, []int{1, 2, 3, 5}, []bool{true, false, false, true})
	n += hitLimiter(2, 1, []int{7, 7, 7}, []bool{true, true, false})
	n += hitLimiter(3, 4, []int{1, 2, 3, 4, 6}, []bool{true, true, true, false, true})
	fmt.Printf("POINTS %d/6\n", n)
}
