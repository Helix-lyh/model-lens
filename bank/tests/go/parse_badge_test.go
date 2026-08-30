package solution

import (
	"fmt"
	"testing"
)

func TestParseBadge(t *testing.T) {
	n := 0
	func() {
		defer func() { recover() }()
		y, m, d, k, ok := ParseBadge("24#08.30+2")
		if ok && y == 2024 && m == 8 && d == 30 && k == 2 {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		y, m, d, k, ok := ParseBadge("00#01.01+0")
		if ok && y == 2000 && m == 1 && d == 1 && k == 0 {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		_, _, _, _, ok := ParseBadge("24#13.01+1")
		if !ok {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		_, _, _, _, ok := ParseBadge("24/08.30+2")
		if !ok {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		_, _, _, _, ok := ParseBadge("23#02.29+1")
		if !ok {
			n++
		}
	}()
	fmt.Printf("POINTS %d/5\n", n)
}
