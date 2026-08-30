package solution

import (
	"fmt"
	"sync"
	"testing"
)

func TestSafeCounter(t *testing.T) {
	n := 0
	func() {
		defer func() { recover() }()
		c := NewSafeCounter()
		var wg sync.WaitGroup
		for i := 0; i < 8; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := 0; j < 200; j++ {
					c.Increment()
				}
			}()
		}
		wg.Wait()
		if c.Value() == 1600 {
			n = 1
		}
	}()
	fmt.Printf("POINTS %d/1\n", n)
}
