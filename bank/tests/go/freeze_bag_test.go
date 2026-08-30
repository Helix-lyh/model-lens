package solution

import (
	"fmt"
	"testing"
)

func TestFreezeBag(t *testing.T) {
	n := 0
	func() {
		defer func() { recover() }()
		bag := NewFreezeBag(2)
		bag.Put("a", 1)
		bag.Put("b", 2)
		if v, ok := bag.Get("a"); ok && v == 1 {
			n++
		}
		bag.Freeze("a")
		bag.Put("c", 3)
		if v, ok := bag.Get("a"); ok && v == 1 {
			n++
		}
		if _, ok := bag.Get("b"); !ok {
			n++
		}
		if v, ok := bag.Get("c"); ok && v == 3 {
			n++
		}
	}()
	fmt.Printf("POINTS %d/4\n", n)
}
